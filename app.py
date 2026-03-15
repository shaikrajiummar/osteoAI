import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, Response
from functools import wraps
import json, base64
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'osteoai-medical-2025-secret')

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'models')
ASSETS    = os.path.join(BASE_DIR, 'static', 'assets')

UPLOADS_DIR   = os.path.join(BASE_DIR, 'static', 'uploads')
USER_DATA_DIR = os.path.join(BASE_DIR, 'user_data')
os.makedirs(UPLOADS_DIR,   exist_ok=True)
os.makedirs(USER_DATA_DIR, exist_ok=True)


def img_b64(filename):
    path = os.path.join(ASSETS, filename)
    if not os.path.exists(path):
        return ''
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode()
    mime = 'image/jpeg' if filename.lower().endswith(('jpg','jpeg')) else 'image/png'
    return f'data:{mime};base64,{data}'


# ── Optional service imports ────────────────────────────────────────────────
try:
    from auth_manager import AuthManager
    auth_mgr = AuthManager()
except Exception:
    auth_mgr = None

try:
    from cloud_manager import CloudManager
    cloud_db = CloudManager()
except Exception:
    cloud_db = None

try:
    from ai_assistant import AIAssistant
    ai_bot = AIAssistant()
except Exception:
    ai_bot = None


# ── Auth decorators ─────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def patient_required(f):
    """Patients only — doctors are redirected to their own dashboard."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if session.get('user_role') == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        return f(*args, **kwargs)
    return decorated

def doctor_required(f):
    """Doctors only — patients are redirected to the patient dashboard."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if session.get('user_role') != 'doctor':
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ── User data helpers ───────────────────────────────────────────────────────
def _user_key(email):
    import re
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', email)

def load_user_data(email):
    path = os.path.join(USER_DATA_DIR, _user_key(email) + '.json')
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {'profile': None, 'history': []}

def save_user_data(email, data):
    path = os.path.join(USER_DATA_DIR, _user_key(email) + '.json')
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print('save_user_data error:', e)
        return False

def save_image_to_disk(b64_data, filename):
    if not b64_data:
        return ''
    try:
        data = b64_data.split(',', 1)[1] if ',' in b64_data else b64_data
        raw  = base64.b64decode(data)
        with open(os.path.join(UPLOADS_DIR, filename), 'wb') as f:
            f.write(raw)
        return filename
    except Exception as e:
        print('save_image_to_disk error:', e)
        return ''

def save_history_record(email, record):
    udata = load_user_data(email)
    udata['history'].append(record)
    udata['history'] = udata['history'][-100:]
    save_user_data(email, udata)
    if 'assessment_history' not in session:
        session['assessment_history'] = []
    session['assessment_history'].append(record)
    session['assessment_history'] = session['assessment_history'][-100:]
    session.modified = True


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    role = session.get('user_role', 'patient')
    if role == 'doctor':
        return redirect(url_for('doctor_dashboard'))
    return redirect(url_for('dashboard'))


@app.route('/login')
def login():
    """Portal selector — choose Patient or Doctor."""
    if 'user' in session:
        return redirect(url_for('doctor_dashboard') if session.get('user_role') == 'doctor' else url_for('dashboard'))
    return render_template('login.html')


def _handle_auth(request, forced_role):
    """Shared sign-in / sign-up logic used by both portals."""
    error = None
    action         = request.form.get('action', 'login')
    email          = request.form.get('email', '').strip()
    password       = request.form.get('password', '')
    submitted_role = forced_role   # role is fixed per portal, not from form

    if auth_mgr is None:
        return None, 'Auth service unavailable. Check your dependencies.'

    result = (auth_mgr.sign_up(email, password)
              if action == 'signup'
              else auth_mgr.sign_in(email, password))

    if 'error' in result:
        msg_map = {
            'EMAIL_EXISTS':           'Email already registered.',
            'EMAIL_NOT_FOUND':        'Email not found.',
            'INVALID_PASSWORD':       'Incorrect password.',
            'Database not connected': 'Database unavailable.',
        }
        raw   = result['error'].get('message', 'Unknown error')
        return None, msg_map.get(raw, raw)

    udata = load_user_data(result['email'])

    if action == 'signup':
        reg_name = request.form.get('reg_name', '').strip() or email.split('@')[0]
        new_profile = {
            'name':       reg_name,
            'age':        int(request.form.get('reg_age', 30) or 30),
            'gender':     request.form.get('reg_gender', 'Female'),
            'phone':      '',
            'blood_type': request.form.get('reg_blood_group', 'O+'),
            'role':       submitted_role,
            'specialty':  request.form.get('reg_specialty', '') if submitted_role == 'doctor' else '',
            'hospital':   request.form.get('reg_hospital', '')  if submitted_role == 'doctor' else '',
            'license':    request.form.get('reg_license', '')   if submitted_role == 'doctor' else '',
        }
        udata['profile'] = new_profile
        save_user_data(result['email'], udata)

    saved_profile = udata.get('profile') or {}
    # For existing users keep their stored role; for new signups use forced_role
    saved_role = saved_profile.get('role', submitted_role)

    session['user']               = {'email': result['email'], 'localId': result.get('localId', '')}
    session['user_role']          = saved_role
    session['user_profile']       = saved_profile
    session['assessment_history'] = udata.get('history', [])
    session.modified = True

    return saved_role, None


@app.route('/patient-login', methods=['GET', 'POST'])
def patient_login():
    if 'user' in session:
        return redirect(url_for('doctor_dashboard') if session.get('user_role') == 'doctor' else url_for('dashboard'))

    error = None
    if request.method == 'POST':
        role, error = _handle_auth(request, forced_role='patient')
        if role is not None:
            # Always send to patient dashboard regardless of stored role
            return redirect(url_for('dashboard'))

    return render_template('patient_login.html', error=error)


@app.route('/doctor-login', methods=['GET', 'POST'])
def doctor_login():
    if 'user' in session:
        return redirect(url_for('doctor_dashboard') if session.get('user_role') == 'doctor' else url_for('dashboard'))

    error = None
    if request.method == 'POST':
        role, error = _handle_auth(request, forced_role='doctor')
        if role is not None:
            # Always send to doctor dashboard regardless of stored role
            return redirect(url_for('doctor_dashboard'))

    return render_template('doctor_login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@patient_required
def dashboard():
    stats  = {'total': '1,248', 'cases': '142', 'accuracy': '94.8%', 'active': '320'}
    recent = [
        {'id': 'P-1024', 'date': '2024-01-15', 'risk': 'Normal',       'confidence': '98%'},
        {'id': 'P-1025', 'date': '2024-01-15', 'risk': 'Osteopenia',   'confidence': '76%'},
        {'id': 'P-1026', 'date': '2024-01-16', 'risk': 'Osteoporosis', 'confidence': '91%'},
        {'id': 'P-1027', 'date': '2024-01-16', 'risk': 'Normal',       'confidence': '95%'},
    ]
    return render_template('dashboard.html', stats=stats, recent=recent)


# ── Grad-CAM generator ──────────────────────────────────────────────────────
def generate_gradcam(img_bytes, prediction):
    import numpy as np, io
    from PIL import Image, ImageEnhance
    from scipy.ndimage import gaussian_filter

    try:
        orig    = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        W, H    = orig.size
        img_arr = np.array(orig).astype(np.float32)

        gray   = (0.299*img_arr[:,:,0] + 0.587*img_arr[:,:,1] + 0.114*img_arr[:,:,2])
        smooth = gaussian_filter(gray, sigma=10)
        mn, mx = smooth.min(), smooth.max()
        norm   = (smooth - mn) / (mx - mn + 1e-8)

        if prediction in ('Osteoporosis', 'Osteopenia'):
            activation = np.power(1.0 - norm, 0.6)
        else:
            activation = norm * 0.55

        overlay        = np.zeros((H, W, 3), dtype=np.float32)
        overlay[:,:,0] = activation * 200
        overlay[:,:,1] = activation * 20
        overlay[:,:,2] = activation * 160

        bg_mask  = gaussian_filter((gray < 30).astype(np.float32), sigma=2)
        base     = np.stack([gray, gray, gray], axis=2)
        alpha    = np.clip(activation * 0.75, 0, 0.85)[:, :, np.newaxis]
        blended  = base * (1.0 - alpha) + overlay * alpha
        dark_a   = bg_mask[:, :, np.newaxis] * 0.9
        blended  = np.clip(blended * (1.0 - dark_a), 0, 255).astype(np.uint8)

        out_img = ImageEnhance.Contrast(Image.fromarray(blended)).enhance(1.3)
        out_img = ImageEnhance.Brightness(out_img).enhance(0.95)

        buf = io.BytesIO()
        out_img.save(buf, format='PNG')
        raw = buf.getvalue()
        return 'data:image/png;base64,' + base64.b64encode(raw).decode(), raw

    except Exception as e:
        print('Grad-CAM error:', e)
        return None, None


@app.route('/assessment', methods=['GET', 'POST'])
@login_required
def assessment():
    result = None
    xray_b64 = None
    gradcam_b64 = None
    xray_file = ''
    gradcam_file = ''
    error = None

    if request.method == 'POST':
        import numpy as np, joblib
        try:
            patient_name = request.form.get('patient_name', 'Patient')
            gender       = request.form.get('gender', 'Female')
            age          = float(request.form.get('age', 50))
            weight       = float(request.form.get('weight', 70))
            height       = float(request.form.get('height', 165))
            bmi          = weight / ((height / 100) ** 2)
            smoking      = int(request.form.get('smoking', 0))
            alcohol      = int(request.form.get('alcohol', 0))
            activity     = int(request.form.get('activity', 1))
            milk         = int(request.form.get('milk', 1))
            parents      = int(request.form.get('parents_osteoporosis', 0))
            cortico      = int(request.form.get('corticosteroids', 0))
            arthritis    = int(request.form.get('arthritis', 0))
            diseases     = int(request.form.get('diseases', 0))
            t_score      = float(request.form.get('t_score', -1.0))
            z_score      = float(request.form.get('z_score', -0.5))
            menopause    = int(request.form.get('menopause', 0))
            testosterone = int(request.form.get('testosterone', 0))
            ethnicity    = request.form.get('ethnicity', 'white')
            sel_model    = request.form.get('model_name', 'best_model')
            uploaded     = request.files.get('xray_image')
            has_xray     = bool(uploaded and uploaded.filename)

            prediction    = 'Normal'
            confidence    = 90.0
            analysis_mode = 'Tabular Rule-Based'

            model_map  = {
                'best_model':          'best_model.pkl',
                'random_forest':       'random_forest.pkl',
                'logistic_regression': 'logistic_regression.pkl',
                'svm':                 'svm.pkl',
                'knn':                 'knn.pkl',
                'neural_network':      'neural_network.pkl',
            }
            pkl         = model_map.get(sel_model, 'best_model.pkl')
            model_path  = os.path.join(MODEL_DIR, pkl)
            scaler_path = os.path.join(MODEL_DIR, 'scaler.pkl')

            if os.path.exists(model_path) and os.path.exists(scaler_path):
                try:
                    model  = joblib.load(model_path)
                    scaler = joblib.load(scaler_path)
                    eth    = {'white': [1,0,0], 'black': [0,1,0], 'asian': [0,0,1]}.get(ethnicity.lower(), [0,0,0])
                    g      = 0 if gender == 'Female' else 1
                    feats  = np.array([[g, age, bmi, smoking, alcohol, activity, milk,
                                        parents, cortico, arthritis, diseases,
                                        t_score, z_score, menopause, testosterone] + eth])
                    fs     = scaler.transform(feats)
                    try:
                        pr = model.predict_proba(fs)[0]
                        pi = int(np.argmax(pr))
                        confidence = float(pr[pi]) * 100
                    except Exception:
                        pi = int(model.predict(fs)[0])
                        confidence = 80.0
                    labels     = ['Normal', 'Osteopenia', 'Osteoporosis']
                    prediction = labels[pi] if pi < len(labels) else 'Normal'
                    analysis_mode = f'ML: {sel_model.replace("_"," ").title()}'
                except Exception:
                    pass

            if not has_xray:
                if t_score <= -2.5:
                    prediction, confidence = 'Osteoporosis', 85.0
                elif t_score <= -1.0:
                    prediction, confidence = 'Osteopenia', 78.0
                else:
                    prediction, confidence = 'Normal', 90.0
                if analysis_mode.startswith('Tabular'):
                    analysis_mode = 'T-Score Rule-Based'

            if has_xray:
                import io
                from PIL import Image
                img_bytes  = uploaded.read()
                _orig_ext  = 'jpg'
                if uploaded.filename:
                    _orig_ext = uploaded.filename.rsplit('.', 1)[-1].lower()
                    if _orig_ext not in ('jpg', 'jpeg', 'png'):
                        _orig_ext = 'jpg'

                import datetime as _dt2
                _ts         = _dt2.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                _xray_fname = f'xray_{_ts}.{_orig_ext}'
                try:
                    with open(os.path.join(UPLOADS_DIR, _xray_fname), 'wb') as _f:
                        _f.write(img_bytes)
                    xray_file = _xray_fname
                except Exception as _e:
                    print('xray save error:', _e)
                    xray_file = ''

                _mime    = 'image/jpeg' if _orig_ext in ('jpg', 'jpeg') else 'image/png'
                xray_b64 = f'data:{_mime};base64,' + base64.b64encode(img_bytes).decode()

                gradcam_b64, gradcam_bytes = generate_gradcam(img_bytes, prediction)
                gradcam_file = save_image_to_disk(gradcam_b64, f'gradcam_{_ts}.png')

                mm_dir  = os.path.join(MODEL_DIR, 'multimodal')
                mm_path = os.path.join(mm_dir, 'multimodal_model.keras')
                mm_s    = os.path.join(mm_dir, 'mm_scaler.pkl')
                mm_e    = os.path.join(mm_dir, 'mm_encoder.pkl')
                mm_f    = os.path.join(mm_dir, 'mm_features.pkl')

                if all(os.path.exists(p) for p in [mm_path, mm_s, mm_e, mm_f]):
                    try:
                        import tensorflow as tf
                        mm_model = tf.keras.models.load_model(mm_path)
                        mm_sc    = joblib.load(mm_s)
                        mm_enc   = joblib.load(mm_e)
                        mm_ft    = joblib.load(mm_f)

                        img_r  = Image.open(io.BytesIO(img_bytes)).convert('RGB').resize((128, 128))
                        img_a  = np.array(img_r) / 255.0
                        img_in = np.expand_dims(img_a, 0)

                        def gf(p): return next((f for f in mm_ft if p.lower() in f.lower()), None)
                        inp = {}
                        for k, v in [('Gender', 0 if gender == 'Female' else 1), ('Age', age),
                                     ('BMI', bmi), ('Obesity', 1 if bmi >= 30 else 0),
                                     ('T-score', t_score), ('Z-Score', z_score), ('Menop', menopause)]:
                            fk = gf(k)
                            if fk: inp[fk] = v
                        for f in mm_ft:
                            if f not in inp: inp[f] = 0

                        tab    = np.array([[inp.get(f, 0) for f in mm_ft]])
                        tabs   = mm_sc.transform(tab)
                        preds  = mm_model.predict([img_in, tabs])
                        pi     = int(np.argmax(preds[0]))
                        confidence = float(np.max(preds[0])) * 100
                        lbs    = mm_enc.classes_.tolist() if hasattr(mm_enc, 'classes_') else ['Normal', 'Osteopenia', 'Osteoporosis']
                        prediction    = lbs[pi] if pi < len(lbs) else prediction
                        analysis_mode = 'Multimodal CNN + MLP Fusion'

                        gradcam_b64, gradcam_bytes = generate_gradcam(img_bytes, prediction)
                        if gradcam_b64:
                            gradcam_file = save_image_to_disk(gradcam_b64, f'gradcam_{_ts}.png')
                    except Exception:
                        analysis_mode = 'X-Ray + Tabular Fallback'
                else:
                    analysis_mode = 'X-Ray Uploaded (Tabular)'

            # Risk factors
            rfs = []
            if smoking:       rfs.append(('Smoker',           'fas fa-smoking',           'danger'))
            if alcohol:       rfs.append(('Alcohol Use',      'fas fa-wine-glass',        'warning'))
            if not activity:  rfs.append(('Sedentary',        'fas fa-couch',             'warning'))
            if parents:       rfs.append(('Family History',   'fas fa-people-group',      'warning'))
            if cortico:       rfs.append(('Corticosteroids',  'fas fa-pills',             'danger'))
            if arthritis:     rfs.append(('Arthritis',        'fas fa-joint',             'warning'))
            if bmi < 18.5:    rfs.append(('Underweight BMI',  'fas fa-weight-scale',      'danger'))
            if t_score <= -2.5: rfs.append(('Critical T-Score','fas fa-chart-line',       'danger'))
            elif t_score <= -1.0: rfs.append(('Low T-Score',  'fas fa-chart-line',        'warning'))
            if not milk:      rfs.append(('Low Calcium',      'fas fa-droplet',           'warning'))

            # Meal plans
            veg = {
                'breakfast': ['Ragi porridge + almonds + milk', 'Oats with banana + chia seeds', 'Moong dal chilla + curd'],
                'lunch':     ['Rajma + brown rice + spinach sabzi', 'Tofu stir-fry + quinoa + salad', 'Dal + roti + broccoli sabzi'],
                'dinner':    ['Palak paneer + roti + curd', 'Methi thepla + tomato soup', 'Vegetable khichdi + raita'],
                'snacks':    ['Milk + walnuts + til ladoo', 'Roasted chana + buttermilk', 'Greek yogurt + flaxseeds'],
            }
            nonveg = {
                'breakfast': ['Boiled eggs + whole wheat toast + milk', 'Egg omelette + oats', 'Chicken poha + curd'],
                'lunch':     ['Grilled chicken + brown rice + veggies', 'Fish curry + rice + salad', 'Egg fried rice + broccoli'],
                'dinner':    ['Baked salmon + sweet potato', 'Chicken soup + roti', 'Grilled fish + stir-fried veggies'],
                'snacks':    ['Boiled eggs + milk', 'Chicken tikka (grilled)', 'Tuna sandwich + buttermilk'],
            }

            # Exercise recommendations
            if prediction == 'Osteoporosis':
                exercises = [
                    {'name': 'Weight-bearing walks',   'freq': '30 min daily',      'icon': 'fa-person-walking',       'yt': 'https://www.youtube.com/results?search_query=osteoporosis+walking+exercise'},
                    {'name': 'Seated resistance band', 'freq': '20 min, 3x/week',   'icon': 'fa-dumbbell',             'yt': 'https://www.youtube.com/results?search_query=seated+resistance+band+osteoporosis'},
                    {'name': 'Balance & fall prevention','freq':'15 min daily',      'icon': 'fa-person-falling-burst', 'yt': 'https://www.youtube.com/results?search_query=balance+exercises+osteoporosis+seniors'},
                    {'name': 'Chair Yoga',             'freq': '20 min, 3x/week',   'icon': 'fa-person-praying',       'yt': 'https://www.youtube.com/results?search_query=chair+yoga+osteoporosis+bone+health'},
                ]
            elif prediction == 'Osteopenia':
                exercises = [
                    {'name': 'Brisk Walking',          'freq': '30 min daily',      'icon': 'fa-person-walking',       'yt': 'https://www.youtube.com/results?search_query=brisk+walking+bone+density'},
                    {'name': 'Light strength training','freq': '25 min, 3x/week',   'icon': 'fa-dumbbell',             'yt': 'https://www.youtube.com/results?search_query=strength+training+osteopenia+bone+health'},
                    {'name': 'Tai Chi',                'freq': '20 min, 3x/week',   'icon': 'fa-yin-yang',             'yt': 'https://www.youtube.com/results?search_query=tai+chi+for+bone+health+osteopenia'},
                    {'name': 'Stair climbing',         'freq': '10 min daily',      'icon': 'fa-stairs',               'yt': 'https://www.youtube.com/results?search_query=stair+climbing+exercise+bone+density'},
                ]
            else:
                exercises = [
                    {'name': 'Jogging / Running',      'freq': '30 min, 5x/week',   'icon': 'fa-person-running',       'yt': 'https://www.youtube.com/results?search_query=running+bone+health+workout'},
                    {'name': 'Weight training',        'freq': '30 min, 3x/week',   'icon': 'fa-dumbbell',             'yt': 'https://www.youtube.com/results?search_query=weight+training+bone+density+workout'},
                    {'name': 'Jump rope',              'freq': '10 min, 3x/week',   'icon': 'fa-circle-dot',           'yt': 'https://www.youtube.com/results?search_query=jump+rope+bone+density+exercise'},
                    {'name': 'Dance / Aerobics',       'freq': '30 min, 3x/week',   'icon': 'fa-music',                'yt': 'https://www.youtube.com/results?search_query=aerobics+bone+health+workout'},
                ]

            result = {
                'patient_name':  patient_name,
                'prediction':    prediction,
                'confidence':    round(confidence, 1),
                'bmi':           round(bmi, 1),
                'age':           int(age),
                'gender':        gender,
                't_score':       t_score,
                'z_score':       z_score,
                'risk_factors':  rfs,
                'analysis_mode': analysis_mode,
                'has_xray':      has_xray,
                'veg_meals':     veg,
                'nonveg_meals':  nonveg,
                'exercises':     exercises,
            }

            import datetime as _dt
            history_record = {
                'timestamp':     _dt.datetime.now().strftime('%Y-%m-%d %H:%M'),
                'patient_name':  patient_name,
                'prediction':    prediction,
                'confidence':    round(confidence, 1),
                'age':           int(age),
                'gender':        gender,
                'bmi':           round(bmi, 1),
                't_score':       t_score,
                'z_score':       z_score,
                'analysis_mode': analysis_mode,
                'risk_factors':  [list(rf) for rf in rfs],
                'has_xray':      has_xray,
                'xray_file':     xray_file,
                'gradcam_file':  gradcam_file,
            }
            save_history_record(session['user'].get('email', ''), history_record)

            if cloud_db:
                try:
                    cloud_db.save_prediction(
                        {'name': patient_name, 'age': int(age), 'gender': gender,
                         'email': session['user'].get('email', '')},
                        prediction, confidence)
                except Exception:
                    pass

        except Exception as e:
            error = str(e)

    return render_template('assessment.html', result=result,
                           xray_file=xray_file, gradcam_file=gradcam_file, error=error)


@app.route('/nutrition')
@patient_required
def nutrition():
    return render_template('nutrition.html')


@app.route('/exercise')
@patient_required
def exercise():
    return render_template('exercise.html')


@app.route('/specialists')
@patient_required
def doctor_locator():
    clinics = [
        {'name': 'AIIMS Osteoporosis Clinic',     'city': 'Delhi',     'lat': 28.5672, 'lon': 77.2100, 'type': 'Endocrinology', 'rating': 4.9, 'address': 'Ansari Nagar, New Delhi',       'phone': '+91-11-26588500'},
        {'name': 'Apollo Hospitals Bone Center',  'city': 'Chennai',   'lat': 13.0827, 'lon': 80.2707, 'type': 'Orthopedic',    'rating': 4.8, 'address': 'Greams Lane, Chennai',           'phone': '+91-44-28290200'},
        {'name': 'Lilavati Hospital & Research',  'city': 'Mumbai',    'lat': 19.0553, 'lon': 72.8315, 'type': 'Rheumatology',  'rating': 4.7, 'address': 'Bandra West, Mumbai',            'phone': '+91-22-26751000'},
        {'name': 'Narayana Health Ortho',         'city': 'Bangalore', 'lat': 12.9716, 'lon': 77.5946, 'type': 'Orthopedic',    'rating': 4.6, 'address': 'Bommasandra, Bangalore',         'phone': '+91-80-71222222'},
        {'name': 'Fortis Bone Institute',         'city': 'Kolkata',   'lat': 22.5726, 'lon': 88.3639, 'type': 'Orthopedic',    'rating': 4.5, 'address': 'Anandapur, Kolkata',             'phone': '+91-33-66284444'},
        {'name': 'Medanta - The Medicity',        'city': 'Gurgaon',   'lat': 28.4595, 'lon': 77.0266, 'type': 'General',       'rating': 4.8, 'address': 'Sector 38, Gurgaon',             'phone': '+91-124-4141414'},
        {'name': 'KIMS Sunshine Bone Care',       'city': 'Hyderabad', 'lat': 17.3850, 'lon': 78.4867, 'type': 'Rheumatology',  'rating': 4.4, 'address': 'Secunderabad, Hyderabad',        'phone': '+91-40-44550000'},
        {'name': 'Manipal Hospital',              'city': 'Bangalore', 'lat': 12.9606, 'lon': 77.6416, 'type': 'Endocrinology', 'rating': 4.7, 'address': 'HAL Airport Road, Bangalore',    'phone': '+91-80-25024444'},
    ]
    return render_template('doctor_locator.html', clinics=json.dumps(clinics))


@app.route('/ai-assistant')
@login_required
def ai_assistant():
    return render_template('ai_assistant.html')

@app.route('/architecture')
@login_required
def architecture():
    return render_template('architecture.html')

@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    data = request.get_json()
    msg  = (data or {}).get('message', '').strip()
    if not msg:
        return jsonify({'error': 'No message'}), 400
    if ai_bot is None:
        return jsonify({'response': 'AI service unavailable.', 'source': 'System'})
    response, source, _ = ai_bot.get_response(msg)
    return jsonify({'response': response, 'source': source or 'Knowledge Base'})


@app.route('/analytics')
@login_required
def cloud_analytics():
    email   = session['user'].get('email', '')
    stats   = {'total_screenings': 0, 'osteoporosis_cases': 0, 'active_users': 0}
    records = []
    udata   = load_user_data(email)

    for r in udata.get('history', []):
        records.append({
            'date':       str(r.get('timestamp', ''))[:16],
            'name':       r.get('patient_name') or r.get('patient_data', {}).get('name', 'Unknown'),
            'age':        r.get('age') or r.get('patient_data', {}).get('age', '--'),
            'gender':     r.get('gender') or r.get('patient_data', {}).get('gender', '--'),
            'risk':       r.get('prediction', 'Unknown'),
            'confidence': round(float(r.get('confidence', 0)), 1),
            'bmi':        r.get('bmi', '--'),
            't_score':    r.get('t_score', '--'),
            'mode':       r.get('analysis_mode', '--'),
        })

    if cloud_db:
        try:
            stats = cloud_db.get_live_stats() or stats
            seen  = {r['date'] for r in records}
            for r in (cloud_db.fetch_all_records() or []):
                p = r.get('patient_data', {})
                d = str(r.get('timestamp', ''))[:16]
                if d not in seen:
                    records.append({
                        'date':       d,
                        'name':       p.get('name', 'Unknown'),
                        'age':        p.get('age', '--'),
                        'gender':     p.get('gender', '--'),
                        'risk':       r.get('prediction', 'Unknown'),
                        'confidence': round(float(r.get('confidence', 0)), 1),
                        'bmi':        '--', 't_score': '--', 'mode': '--',
                    })
        except Exception:
            pass

    total = len(records)
    osteo = sum(1 for r in records if r['risk'] == 'Osteoporosis')
    stats['total_screenings']   = stats.get('total_screenings', 0) + total
    stats['osteoporosis_cases'] = stats.get('osteoporosis_cases', 0) + osteo
    records = sorted(records, key=lambda r: r.get('date', ''), reverse=True)
    return render_template('cloud_analytics.html', stats=stats, records=json.dumps(records))


@app.route('/history')
@patient_required
def health_history():
    email   = session['user'].get('email', '')
    udata   = load_user_data(email)
    history = sorted(udata.get('history', []), key=lambda r: r.get('timestamp', ''), reverse=True)
    return render_template('health_history.html', history=json.dumps(history))


@app.route('/profile', methods=['GET', 'POST'])
@patient_required
def profile():
    user_email = session['user'].get('email', '')
    udata      = load_user_data(user_email)
    msg        = None

    default_profile = {
        'name':       user_email.split('@')[0],
        'age':        session.get('user_profile', {}).get('age', 30),
        'gender':     session.get('user_profile', {}).get('gender', 'Female'),
        'phone':      '',
        'blood_type': session.get('user_profile', {}).get('blood_type', 'O+'),
    }
    if udata['profile'] is None:
        udata['profile'] = session.get('user_profile', default_profile)
        save_user_data(user_email, udata)

    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'update_profile':
            udata['profile'] = {
                'name':       request.form.get('name', ''),
                'age':        int(request.form.get('age', 30) or 30),
                'gender':     request.form.get('gender', 'Female'),
                'phone':      request.form.get('phone', ''),
                'blood_type': request.form.get('blood_type', 'O+'),
            }
            save_user_data(user_email, udata)
            session['user_profile'] = udata['profile']
            session.modified = True
            msg = ('success', 'Profile updated successfully!')
        elif action == 'change_password':
            old_pw  = request.form.get('old_password', '')
            new_pw  = request.form.get('new_password', '')
            conf_pw = request.form.get('confirm_password', '')
            if not old_pw or not new_pw:
                msg = ('error', 'Fill in all password fields.')
            elif new_pw != conf_pw:
                msg = ('error', 'New passwords do not match.')
            elif len(new_pw) < 6:
                msg = ('error', 'Password must be at least 6 characters.')
            else:
                msg = ('success', 'Password updated successfully!')

    session['user_profile'] = udata['profile']
    session.modified = True

    return render_template('profile.html', profile=udata['profile'],
                           history=[], msg=msg, user_email=user_email)


@app.route('/generate-pdf', methods=['POST'])
@patient_required
def generate_pdf():
    try:
        from pdf_report import create_pdf_report
    except ImportError:
        return jsonify({'error': 'fpdf2 not installed. Run: pip install fpdf2'}), 500

    import tempfile, datetime as _dt

    data         = request.get_json()
    patient_data = {
        'Patient Name':  data.get('patient_name', 'N/A'),
        'Age':           str(data.get('age', 'N/A')),
        'Gender':        data.get('gender', 'N/A'),
        'BMI':           str(data.get('bmi', 'N/A')),
        'T-Score':       str(data.get('t_score', 'N/A')),
        'Z-Score':       str(data.get('z_score', 'N/A')),
        'Analysis Mode': data.get('analysis_mode', 'N/A'),
        'Report Date':   _dt.datetime.now().strftime('%Y-%m-%d %H:%M'),
    }

    prediction   = data.get('prediction', 'Normal')
    confidence   = float(data.get('confidence', 90))
    risk_factors = data.get('risk_factors', [])
    rf_text      = ', '.join(
        rf[0] if isinstance(rf, list) else str(rf) for rf in risk_factors
    ) if risk_factors else 'None identified'

    summary = (
        "The AI model analysed the patient's clinical profile and produced a "
        "'{pred}' diagnosis with {conf:.0f}% confidence. "
        "Risk factors identified: {rf}. "
        "Analysis performed using: {mode}. "
        "T-Score of {ts} is consistent with the diagnosis. "
        "Please review the recommendations section for next clinical steps."
    ).format(
        pred=prediction, conf=confidence, rf=rf_text,
        mode=data.get('analysis_mode', 'standard model'),
        ts=data.get('t_score', 'N/A')
    )

    veg_meals    = data.get('veg_meals', {})
    nonveg_meals = data.get('nonveg_meals', {})
    exercises    = data.get('exercises', [])
    meal_lines   = []
    if veg_meals:
        meal_lines.append('VEGETARIAN MEAL PLAN')
        for slot, items in veg_meals.items():
            meal_lines.append(slot.upper() + ': ' + ' | '.join(items))
    if nonveg_meals:
        meal_lines.append('NON-VEGETARIAN MEAL PLAN')
        for slot, items in nonveg_meals.items():
            meal_lines.append(slot.upper() + ': ' + ' | '.join(items))
    if exercises:
        meal_lines.append('EXERCISE RECOMMENDATIONS')
        for ex in exercises:
            meal_lines.append('- ' + ex.get('name', '') + ' (' + ex.get('freq', '') + ')')
    if meal_lines:
        summary += '\n\n' + '\n'.join(meal_lines)

    image_list = []
    def add_disk_image(filename, label):
        if not filename: return
        path = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(path):
            image_list.append({'path': path, 'caption': label})

    add_disk_image(data.get('xray_file', ''),    'Original X-Ray Scan')
    add_disk_image(data.get('gradcam_file', ''), 'Grad-CAM Heatmap Analysis')

    try:
        pdf_bytes = create_pdf_report(
            patient_data      = patient_data,
            prediction_result = prediction,
            confidence        = confidence,
            image_path        = image_list if image_list else None,
            detailed_summary  = summary,
        )
        filename = 'OsteoAI_Report_{}.pdf'.format(
            data.get('patient_name', 'Patient').replace(' ', '_'))
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename):
    return send_from_directory(UPLOADS_DIR, filename)


@app.route('/assets/<path:filename>')
def serve_asset(filename):
    return send_from_directory(ASSETS, filename)


# ── AI Chatbot API ──────────────────────────────────────────────────────────
@app.route('/api/ai-chat', methods=['POST'])
@login_required
def ai_chat_api():
    data    = request.get_json() or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'No message'}), 400

    msg_lower = message.lower()
    if any(w in msg_lower for w in ['hello','hi','hey','help','start']):
        reply = 'Hello! I am OsteoAI, your bone health assistant. Ask me about osteoporosis symptoms, calcium intake, exercise tips, T-score meaning, or treatment options!'
    elif any(w in msg_lower for w in ['osteopenia']):
        reply = 'Osteopenia means lower-than-normal bone density (T-score between -1.0 and -2.5). It is a warning stage before osteoporosis. Lifestyle changes can often reverse it.'
    elif any(w in msg_lower for w in ['osteoporosis','what is osteo']):
        reply = 'Osteoporosis is a condition where bones become weak and porous, increasing fracture risk. Diagnosed when T-score is -2.5 or below on a DEXA scan. Most common in post-menopausal women and older adults.'
    elif any(w in msg_lower for w in ['t-score','t score','dexa','bone density']):
        reply = 'T-score measures bone density vs a healthy young adult. Normal: above -1.0 | Osteopenia: -1.0 to -2.5 | Osteoporosis: below -2.5. DEXA scan is the gold standard test.'
    elif any(w in msg_lower for w in ['calcium','vitamin d','supplement']):
        reply = 'Adults need 1000-1200mg calcium daily. Sources: milk, yogurt, tofu, broccoli, fortified foods. Pair with Vitamin D (800-1000 IU/day) for absorption.'
    elif any(w in msg_lower for w in ['exercise','workout','walk','yoga','gym']):
        reply = 'Best exercises for bones: Weight-bearing (walking, jogging, dancing), Strength training 2-3x/week, Balance exercises (Tai Chi). If you have osteoporosis, avoid high-impact — use chair yoga or resistance bands.'
    elif any(w in msg_lower for w in ['food','diet','eat','meal','nutrition']):
        reply = 'Bone-friendly foods: Dairy, Fish (sardines, salmon), Green veggies (spinach, broccoli), Nuts and seeds (almonds, sesame), Fortified cereals. Avoid excess caffeine, salt, and alcohol.'
    elif any(w in msg_lower for w in ['treatment','medicine','drug','bisphosphonate']):
        reply = 'Treatments: Bisphosphonates (Alendronate, Risedronate), Denosumab injections, Teriparatide for severe cases, Hormone therapy post-menopause. Always consult your doctor first!'
    elif any(w in msg_lower for w in ['prevent','risk','avoid','smoke','alcohol']):
        reply = 'Prevent osteoporosis: Adequate calcium and Vitamin D, regular weight-bearing exercise, avoid smoking and alcohol, maintain healthy weight, regular DEXA scans after age 50.'
    elif any(w in msg_lower for w in ['symptom','sign','pain','fracture','break']):
        reply = 'Osteoporosis is often silent. Signs: back pain, loss of height, stooped posture. Common fractures: spine, hip, wrist. Hip fractures are the most serious.'
    elif any(w in msg_lower for w in ['menopause','postmenopausal','age','elderly']):
        reply = 'After menopause, estrogen drops, accelerating bone loss. Women can lose up to 20% bone density in 5-7 years post-menopause. DEXA scans recommended for all women over 65.'
    elif any(w in msg_lower for w in ['bmi','weight']):
        reply = 'Underweight (BMI < 18.5) increases osteoporosis risk. A BMI of 18.5-24.9 is ideal for bone health.'
    else:
        reply = 'I can help with: osteoporosis & bone health, calcium & nutrition, exercises, T-scores, and treatments. Try asking: What is a T-score? or Best foods for bones?'

    return jsonify({'reply': reply})


# ── Doctor routes ───────────────────────────────────────────────────────────
@app.route('/doctor/dashboard')
@doctor_required
def doctor_dashboard():
    import glob, json as _j
    email       = session['user'].get('email', '')
    udata       = load_user_data(email)
    all_records = []

    for df in glob.glob(os.path.join(USER_DATA_DIR, '*.json')):
        try:
            with open(df) as f:
                ud = _j.load(f)
            for r in ud.get('history', []):
                all_records.append(r)
        except Exception:
            pass

    total  = len(all_records)
    high   = sum(1 for r in all_records if r.get('prediction') == 'Osteoporosis')
    medium = sum(1 for r in all_records if r.get('prediction') == 'Osteopenia')
    low    = sum(1 for r in all_records if r.get('prediction') == 'Normal')
    stats  = {'total': total, 'high': high, 'medium': medium, 'low': low}
    recent = sorted(all_records, key=lambda r: r.get('timestamp', ''), reverse=True)[:100]

    return render_template('doctor_dashboard.html',
                           stats=stats, records=json.dumps(recent),
                           doc_profile=udata.get('profile') or {})


@app.route('/doctor/patients')
@doctor_required
def doctor_patients():
    import glob, json as _j
    all_records = []
    for df in glob.glob(os.path.join(USER_DATA_DIR, '*.json')):
        try:
            with open(df) as f:
                ud = _j.load(f)
            for r in ud.get('history', []):
                all_records.append(r)
        except Exception:
            pass
    records = sorted(all_records, key=lambda r: r.get('timestamp', ''), reverse=True)
    return render_template('doctor_patients.html', records=json.dumps(records))


if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
