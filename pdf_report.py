"""
OsteoAI — Premium Clinical PDF Report
Full-page cover + official medical interior with colourful borders
"""
import io, os, datetime, math

NAVY=(0.03,0.09,0.24);NAVY2=(0.06,0.14,0.34);NAVY3=(0.09,0.20,0.46)
BLUE=(0.10,0.44,0.77);BLUE2=(0.18,0.54,0.90);SKYBLUE=(0.55,0.80,0.98)
SILVER=(0.95,0.97,1.00);SILVER2=(0.88,0.92,0.98);BORDER=(0.78,0.86,0.95)
DARK=(0.08,0.11,0.16);MUTED=(0.40,0.47,0.58);WHITE=(1.00,1.00,1.00)
GREEN=(0.02,0.54,0.30);GREENBG=(0.90,0.98,0.93);GREENBD=(0.55,0.88,0.68)
AMBER=(0.54,0.33,0.00);AMBERBG=(1.00,0.97,0.87);AMBERBD=(0.95,0.76,0.28)
RED=(0.70,0.07,0.07);REDBG=(1.00,0.93,0.93);REDBD=(0.92,0.56,0.56)
TEAL=(0.04,0.60,0.54);TEAL2=(0.02,0.42,0.38);CYAN=(0.00,0.74,0.84)
PURPLE=(0.36,0.18,0.62);GOLD=(0.82,0.65,0.10);GOLD2=(0.96,0.85,0.40)
ORANGE=(0.85,0.38,0.04)

PW=595.27;PH=841.89;ML=46;MR=46;CW=PW-ML-MR
TOP_MARGIN=88;BOT_MARGIN=52

def _col(t):
    from reportlab.lib import colors
    return colors.Color(*t)

def _rr(cv,x,y,w,h,r,fill=None,stroke=None,lw=0.6):
    if fill: cv.setFillColorRGB(*fill)
    if stroke: cv.setStrokeColorRGB(*stroke);cv.setLineWidth(lw)
    cv.roundRect(x,y,w,h,r,fill=1 if fill else 0,stroke=1 if stroke else 0)

def _bone(cv,cx,cy,sz=24,col=WHITE):
    cv.saveState();cv.translate(cx,cy);cv.setFillColorRGB(*col)
    sw=sz*0.22;sh=sz*1.02
    cv.roundRect(-sw/2,-sh/2,sw,sh,sw/2,fill=1,stroke=0)
    hw=sz*1.02;hh=sz*0.22
    cv.roundRect(-hw/2,-hh/2,hw,hh,hh/2,fill=1,stroke=0)
    kr=sz*0.29
    for ex,ey in [(-hw/2,0),(hw/2,0),(0,-sh/2),(0,sh/2)]:
        cv.circle(ex,ey,kr,fill=1,stroke=0)
    cv.restoreState()

def _dna(cv,x,y,h,c1,c2,step=20,dr=2.2):
    for i in range(int(h/step)):
        fy=y+i*step;ang=math.radians(i*30);ox=math.sin(ang)*8
        cv.setFillColorRGB(*c1);cv.circle(x+ox,fy,dr,fill=1,stroke=0)
        cv.setFillColorRGB(*c2);cv.circle(x-ox,fy+step/2,dr,fill=1,stroke=0)

def _gauge(cv,cx,cy,ts,R=56,r=34):
    def t2a(t): return 180.0-(max(-4.0,min(2.0,t))+4.0)/6.0*180.0
    def arc(a0,a1,col):
        cv.setFillColorRGB(*col);steps=32
        path=cv.beginPath()
        a0r=math.radians(a0);a1r=math.radians(a1)
        path.moveTo(R*math.cos(a0r),R*math.sin(a0r))
        for i in range(1,steps+1):
            a=a0r+(a1r-a0r)*i/steps;path.lineTo(R*math.cos(a),R*math.sin(a))
        a=a1r;path.lineTo(r*math.cos(a),r*math.sin(a))
        for i in range(steps,-1,-1):
            a=a0r+(a1r-a0r)*i/steps;path.lineTo(r*math.cos(a),r*math.sin(a))
        path.close();cv.drawPath(path,fill=1,stroke=0)
    cv.saveState();cv.translate(cx,cy)
    for t0,t1,col in [(-4.0,-2.5,RED),(-2.5,-1.0,AMBER),(-1.0,2.0,GREEN)]:
        arc(t2a(t1),t2a(t0),col)
    cv.setFillColorRGB(*WHITE);cv.circle(0,0,r-2,fill=1,stroke=0)
    na=math.radians(t2a(ts));nl=R-4
    cv.setStrokeColorRGB(*DARK);cv.setLineWidth(2.2);cv.line(0,0,nl*math.cos(na),nl*math.sin(na))
    cv.setFillColorRGB(*NAVY);cv.circle(0,0,5,fill=1,stroke=0)
    cv.setFillColorRGB(*WHITE);cv.circle(0,0,2.5,fill=1,stroke=0)
    cv.setFont('Helvetica-Bold',10);cv.setFillColorRGB(*DARK);cv.drawCentredString(0,-r+4,f'T = {ts:+.1f}')
    cv.setFont('Helvetica',5.8)
    cv.setFillColorRGB(*RED);cv.drawCentredString(-40,-18,'Osteoporosis')
    cv.setFillColorRGB(*AMBER);cv.drawCentredString(0,R-8,'Osteopenia')
    cv.setFillColorRGB(*GREEN);cv.drawCentredString(40,-18,'Normal')
    cv.restoreState()

def _frax(cv,x,y,w,frax):
    h=46;_rr(cv,x,y,w,h,6,fill=SILVER,stroke=BORDER)
    col=RED if frax>=20 else(AMBER if frax>=10 else GREEN)
    pct=min(frax/40.0,1.0);bw=(w-16)*pct
    _rr(cv,x+8,y+10,w-16,8,3,fill=BORDER)
    if bw>1:_rr(cv,x+8,y+10,bw,8,3,fill=col)
    cv.setFont('Helvetica-Bold',7.5);cv.setFillColorRGB(*NAVY)
    cv.drawString(x+8,y+28,'10-Year Fracture Probability (FRAX):')
    cv.setFont('Helvetica-Bold',9);cv.setFillColorRGB(*col)
    rl='HIGH RISK' if frax>=20 else('MODERATE' if frax>=10 else 'LOW RISK')
    cv.drawRightString(x+w-8,y+28,f'{frax:.1f}%  —  {rl}')

def create_pdf_report(patient_data:dict,prediction_result:str,confidence:float,
                      image_path=None,detailed_summary:str='')->bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (BaseDocTemplate,Frame,PageTemplate as PT,
        NextPageTemplate,PageBreak,Paragraph,Spacer,Table,TableStyle,
        HRFlowable,KeepTogether,Image as RLImage,Flowable)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT,TA_CENTER,TA_RIGHT,TA_JUSTIFY

    buf=io.BytesIO();now=datetime.datetime.now()
    rdate=patient_data.get('Report Date',now.strftime('%d %B %Y,  %H:%M'))
    rid=f'OAI-{now.strftime("%Y%m%d")}-{abs(hash(patient_data.get("Patient Name","X")))%9000+1000}'
    pname=patient_data.get('Patient Name','Patient')
    pred=(prediction_result or 'Normal').strip()
    conf=min(max(float(confidence),0),100)
    try: ts=float(patient_data.get('T-Score',0))
    except: ts=0.0
    try: age_n=int(patient_data.get('Age',60))
    except: age_n=60
    frax_val=round(min(max(0,(age_n-50)*0.3-ts*2.5),40.0),1)

    if pred=='Normal':
        dfc,dbg,dbd=GREEN,GREENBG,GREENBD
        sev='LOW RISK — NORMAL BONE DENSITY';sev_s='Normal'
        ddesc=('Bone mineral density is within the normal reference range for age and sex. '
               'Continue preventive strategies and schedule routine DEXA surveillance per clinical guidelines.')
    elif pred=='Osteopenia':
        dfc,dbg,dbd=AMBER,AMBERBG,AMBERBD
        sev='MODERATE RISK — OSTEOPENIA';sev_s='Osteopenia'
        ddesc=('Bone density is below the normal reference range but above the osteoporosis threshold. '
               'Lifestyle modification and closer clinical monitoring are strongly recommended.')
    else:
        pred='Osteoporosis';dfc,dbg,dbd=RED,REDBG,REDBD
        sev='HIGH RISK — OSTEOPOROSIS';sev_s='Osteoporosis'
        ddesc=('Bone mineral density is critically reduced. Immediate specialist referral, '
               'pharmacotherapy initiation, and fall-prevention measures are urgently required.')

    def S(n,**kw): return ParagraphStyle(n,**kw)
    sH=S('H',fontName='Helvetica-Bold',fontSize=10,textColor=_col(NAVY),leading=14,spaceBefore=8,spaceAfter=3)
    sLb=S('Lb',fontName='Helvetica-Bold',fontSize=7,textColor=_col(MUTED),leading=10)
    sV=S('V',fontName='Helvetica',fontSize=9,textColor=_col(DARK),leading=13)
    sBV=S('BV',fontName='Helvetica-Bold',fontSize=9.5,textColor=_col(DARK),leading=13)
    sBy=S('By',fontName='Helvetica',fontSize=8.8,textColor=_col(DARK),leading=14,spaceAfter=4,alignment=TA_JUSTIFY)
    sCp=S('Cp',fontName='Helvetica-Oblique',fontSize=7.5,textColor=_col(MUTED),leading=10,alignment=TA_CENTER)
    sDi=S('Di',fontName='Helvetica',fontSize=7,textColor=_col(MUTED),leading=11,alignment=TA_JUSTIFY)
    sSm=S('Sm',fontName='Helvetica',fontSize=7.5,textColor=_col(DARK),leading=11)
    sTg=S('Tg',fontName='Helvetica-Bold',fontSize=7,textColor=_col(WHITE),leading=10)

    # ═══════════════════════════════════════════════════════
    #  COVER PAGE
    # ═══════════════════════════════════════════════════════
    def draw_cover(cv,doc):
        cv.saveState()

        # ── Background ──────────────────────────────────────
        cv.setFillColorRGB(*NAVY);cv.rect(0,0,PW,PH,fill=1,stroke=0)
        cv.setFillColorRGB(*NAVY2);cv.rect(0,PH*0.48,PW,PH*0.52,fill=1,stroke=0)

        # Large decorative circles
        cv.setFillColorRGB(*BLUE2);cv.setFillAlpha(0.07)
        cv.circle(PW-10,PH-10,210,fill=1,stroke=0)
        cv.setFillAlpha(0.04);cv.circle(PW-80,PH*0.30,150,fill=1,stroke=0)
        cv.setFillAlpha(0.03);cv.circle(50,100,110,fill=1,stroke=0)
        cv.setFillAlpha(1.0)

        # ── Left gradient bar ────────────────────────────────
        bw=10
        for i in range(int(PH)):
            f=i/PH
            cv.setFillColorRGB(TEAL[0]*(1-f)+BLUE[0]*f,
                               TEAL[1]*(1-f)+BLUE[1]*f,
                               TEAL[2]*(1-f)+BLUE2[2]*f)
            cv.rect(0,i,bw,1,fill=1,stroke=0)

        # ── Right gold bar ───────────────────────────────────
        cv.setFillColorRGB(*GOLD);cv.rect(PW-6,0,6,PH,fill=1,stroke=0)

        # ── Top multi-colour band ────────────────────────────
        seg=PW/5
        for i,c in enumerate([TEAL,BLUE2,PURPLE,GOLD,ORANGE]):
            cv.setFillColorRGB(*c);cv.rect(i*seg,PH-6,seg,6,fill=1,stroke=0)

        # ── Bottom multi-colour band ─────────────────────────
        for i,c in enumerate([TEAL,BLUE2,PURPLE,GOLD,ORANGE]):
            cv.setFillColorRGB(*c);cv.rect(i*seg,0,seg,5,fill=1,stroke=0)

        # ── DNA decoration right side ────────────────────────
        _dna(cv,PW-25,PH*0.12,PH*0.70,(0.18,0.62,0.90),(0.04,0.60,0.54),step=20,dr=2.2)

        # ════════════════════════════════════════════════════
        #  BIG LOGO
        # ════════════════════════════════════════════════════
        lx=bw+14;ly=PH-118;isz=80

        # Halo
        cv.setFillColorRGB(*TEAL);cv.setFillAlpha(0.14)
        cv.roundRect(lx-7,ly-7,isz+14,isz+14,22,fill=1,stroke=0);cv.setFillAlpha(1.0)

        # Icon box
        cv.setFillColorRGB(0.04,0.20,0.52)
        cv.roundRect(lx,ly,isz,isz,17,fill=1,stroke=0)
        cv.setStrokeColorRGB(*TEAL);cv.setLineWidth(2.2)
        cv.roundRect(lx+3,ly+3,isz-6,isz-6,14,fill=0,stroke=1)

        # Big bone icon
        _bone(cv,lx+isz/2,ly+isz/2+3,sz=28,col=WHITE)

        # AI badge
        cv.setFillColorRGB(*TEAL)
        cv.roundRect(lx+isz-24,ly-3,26,17,4,fill=1,stroke=0)
        cv.setFont('Helvetica-Bold',8);cv.setFillColorRGB(*WHITE)
        cv.drawCentredString(lx+isz-11,ly+2,'AI')

        # Brand text
        tx=lx+isz+18
        cv.setFont('Helvetica-Bold',38);cv.setFillColorRGB(*WHITE)
        cv.drawString(tx,ly+46,'OsteoAI')
        # Cyan accent on first word
        cv.setFont('Helvetica-Bold',38);cv.setFillColorRGB(*CYAN)
        cv.drawString(tx,ly+46,'Osteo')
        cv.setFont('Helvetica-Bold',38);cv.setFillColorRGB(*WHITE)
        cv.drawString(tx+130,ly+46,'AI')

        # Teal underline
        cv.setStrokeColorRGB(*TEAL);cv.setLineWidth(3)
        cv.line(tx,ly+41,tx+178,ly+41)

        cv.setFont('Helvetica-Bold',10);cv.setFillColorRGB(*TEAL)
        cv.drawString(tx,ly+26,'BONE DENSITY DIAGNOSTIC PLATFORM')
        cv.setFont('Helvetica',8.5);cv.setFillColorRGB(0.60,0.76,0.93)
        cv.drawString(tx,ly+12,'AI-Powered Clinical Analysis  ·  Multimodal Bone Health Assessment')

        # Separator
        sy=ly-16
        cv.setStrokeColorRGB(*TEAL);cv.setStrokeAlpha(0.28);cv.setLineWidth(0.8)
        cv.line(bw+8,sy,PW-20,sy);cv.setStrokeAlpha(1.0)

        # ════════════════════════════════════════════════════
        #  TITLE BLOCK
        # ════════════════════════════════════════════════════
        ty=PH*0.595

        # Subtle band behind title
        cv.setFillColorRGB(*NAVY3);cv.setFillAlpha(0.55)
        cv.roundRect(bw+6,ty-8,PW-bw-24,78,8,fill=1,stroke=0);cv.setFillAlpha(1.0)

        # "Diagnostic" in cyan, "Report" in white
        cv.setFont('Helvetica-Bold',36);cv.setFillColorRGB(*CYAN)
        cv.drawString(ML,ty+32,'Diagnostic')
        cv.setFont('Helvetica-Bold',36);cv.setFillColorRGB(*WHITE)
        cv.drawString(ML+212,ty+32,' Report')

        cv.setFont('Helvetica',12);cv.setFillColorRGB(0.60,0.76,0.94)
        cv.drawString(ML,ty+12,'Bone Mineral Density Assessment  ·  Clinical Analysis  ·  Treatment Plan')

        # Four-colour gradient underline
        for i,c in enumerate([TEAL,BLUE2,PURPLE,GOLD]):
            cv.setStrokeColorRGB(*c);cv.setLineWidth(3.5)
            cv.line(ML+i*62,ty,ML+i*62+60,ty)

        # ════════════════════════════════════════════════════
        #  PATIENT CARD
        # ════════════════════════════════════════════════════
        cy2=ty-228;ch=164;cw2=CW;cx2=ML

        # Shadow
        cv.setFillColorRGB(0,0,0);cv.setFillAlpha(0.22)
        cv.roundRect(cx2+5,cy2-5,cw2,ch,14,fill=1,stroke=0);cv.setFillAlpha(1.0)

        # Card body
        cv.setFillColorRGB(1,1,1);cv.setFillAlpha(0.07)
        cv.roundRect(cx2,cy2,cw2,ch,12,fill=1,stroke=0);cv.setFillAlpha(1.0)

        # Left diagnosis-colour bar
        cv.setFillColorRGB(*dfc)
        cv.roundRect(cx2,cy2,7,ch,3,fill=1,stroke=0)

        # Card border teal
        cv.setStrokeColorRGB(*TEAL);cv.setStrokeAlpha(0.22);cv.setLineWidth(1.0)
        cv.roundRect(cx2,cy2,cw2,ch,12,fill=0,stroke=1);cv.setStrokeAlpha(1.0)

        # Card header
        cv.setFillColorRGB(*NAVY3);cv.setFillAlpha(0.82)
        cv.roundRect(cx2,cy2+ch-33,cw2,33,12,fill=1,stroke=0);cv.setFillAlpha(1.0)
        cv.setFont('Helvetica-Bold',7.5);cv.setFillColorRGB(*TEAL)
        cv.drawString(cx2+16,cy2+ch-21,'PATIENT CLINICAL RECORD')
        cv.setFont('Helvetica',7);cv.setFillColorRGB(0.50,0.66,0.86)
        cv.drawRightString(cx2+cw2-14,cy2+ch-21,f'Report ID: {rid}   ·   {rdate[:16]}')

        # 3-column fields
        fields=[
            ('PATIENT NAME',        pname),
            ('AGE / GENDER',        f'{patient_data.get("Age","—")}  ·  {patient_data.get("Gender","—")}'),
            ('T-SCORE / Z-SCORE',   f'{patient_data.get("T-Score","—")}  /  {patient_data.get("Z-Score","—")}'),
            ('BMI',                 patient_data.get('BMI','—')),
            ('REFERRING PHYSICIAN', patient_data.get('Referring Physician','—')),
            ('HOSPITAL / CLINIC',   patient_data.get('Hospital/Clinic','—')),
        ]
        fw=cw2/3
        for ci,cf in enumerate([fields[0:2],fields[2:4],fields[4:6]]):
            fx=cx2+16+ci*fw;fy=cy2+ch-52
            for lbl,val in cf:
                cv.setFont('Helvetica-Bold',5.8);cv.setFillColorRGB(0.46,0.66,0.88)
                cv.drawString(fx,fy,lbl)
                dv=str(val);dv=dv[:30]+'…' if len(dv)>32 else dv
                cv.setFont('Helvetica-Bold',9.5);cv.setFillColorRGB(*WHITE)
                cv.drawString(fx,fy-14,dv);fy-=46
            if ci<2:
                cv.setStrokeColorRGB(1,1,1);cv.setStrokeAlpha(0.08);cv.setLineWidth(0.6)
                cv.line(cx2+(ci+1)*fw,cy2+8,cx2+(ci+1)*fw,cy2+ch-36)
                cv.setStrokeAlpha(1.0)

        # ════════════════════════════════════════════════════
        #  DIAGNOSIS + CONFIDENCE BADGES
        # ════════════════════════════════════════════════════
        bx=cx2;by2=cy2-70;bh2=56
        bw1=CW*0.60;bw2=CW-bw1-10

        # Diagnosis pill
        cv.setFillColorRGB(*dfc);cv.roundRect(bx,by2,bw1,bh2,10,fill=1,stroke=0)
        cv.setFillColorRGB(1,1,1);cv.setFillAlpha(0.09)
        cv.roundRect(bx,by2+bh2*0.55,bw1,bh2*0.45,10,fill=1,stroke=0);cv.setFillAlpha(1.0)
        # Circle icon
        cv.setFillColorRGB(1,1,1);cv.setFillAlpha(0.18)
        cv.circle(bx+26,by2+bh2/2,14,fill=1,stroke=0);cv.setFillAlpha(1.0)
        sym='✓' if pred=='Normal' else('!' if pred=='Osteopenia' else '⚠')
        cv.setFont('Helvetica-Bold',18);cv.setFillColorRGB(*WHITE)
        cv.drawCentredString(bx+26,by2+bh2/2-6,sym)
        cv.setFont('Helvetica',7.5);cv.setFillColorRGB(1,1,1);cv.setFillAlpha(0.80)
        cv.drawString(bx+48,by2+bh2-16,'AI DIAGNOSIS RESULT');cv.setFillAlpha(1.0)
        cv.setFont('Helvetica-Bold',13);cv.setFillColorRGB(*WHITE)
        cv.drawString(bx+48,by2+bh2-33,sev[:38])
        cv.setFont('Helvetica',7.5);cv.setFillColorRGB(1,1,1);cv.setFillAlpha(0.72)
        cv.drawString(bx+48,by2+10,f'T-Score: {patient_data.get("T-Score","—")}  ·  WHO Classification')
        cv.setFillAlpha(1.0)

        # Confidence pill
        bx2c=bx+bw1+10
        cv.setFillColorRGB(0.05,0.14,0.34);cv.roundRect(bx2c,by2,bw2,bh2,10,fill=1,stroke=0)
        cv.setStrokeColorRGB(*GOLD);cv.setLineWidth(1.8)
        cv.roundRect(bx2c,by2,bw2,bh2,10,fill=0,stroke=1)
        cv.setFont('Helvetica-Bold',8);cv.setFillColorRGB(*GOLD)
        cv.drawCentredString(bx2c+bw2/2,by2+bh2-15,'MODEL CONFIDENCE')
        cv.setFont('Helvetica-Bold',30);cv.setFillColorRGB(*WHITE)
        cv.drawCentredString(bx2c+bw2/2,by2+10,f'{conf:.0f}%')

        # ── Feature tags ──────────────────────────────────────
        tags=[(TEAL,f'FRAX: {frax_val:.1f}%  10-yr Risk'),
              (BLUE,patient_data.get('Analysis Mode','Standard')),
              (PURPLE,'AI-Powered Diagnosis'),(GOLD,'CONFIDENTIAL')]
        tx3=cx2;ty3=by2-34
        for tc,tt in tags:
            tw=len(tt)*5.8+20
            cv.setFillColorRGB(*tc);cv.setFillAlpha(0.18)
            cv.roundRect(tx3,ty3,tw,20,4,fill=1,stroke=0);cv.setFillAlpha(1.0)
            cv.setStrokeColorRGB(*tc);cv.setLineWidth(0.8)
            cv.roundRect(tx3,ty3,tw,20,4,fill=0,stroke=1)
            cv.setFont('Helvetica-Bold',7);cv.setFillColorRGB(*tc)
            cv.drawString(tx3+9,ty3+6,tt);tx3+=tw+8

        # ════════════════════════════════════════════════════
        #  FOOTER METADATA STRIP
        # ════════════════════════════════════════════════════
        fh=52
        cv.setFillColorRGB(0.04,0.10,0.24);cv.rect(0,0,PW,fh,fill=1,stroke=0)
        seg2=PW/4
        for i,c in enumerate([TEAL,BLUE2,PURPLE,GOLD]):
            cv.setFillColorRGB(*c);cv.rect(i*seg2,fh-3,seg2,3,fill=1,stroke=0)
        meta=[('REPORT ID',rid),
              ('DATE ISSUED',rdate[:16] if len(rdate)>16 else rdate),
              ('ANALYSIS',patient_data.get('Analysis Mode','Standard')[:22]),
              ('STATUS','CONFIDENTIAL')]
        for i,(lbl,val) in enumerate(meta):
            mx=ML+i*(CW/4)
            if i>0:
                cv.setStrokeColorRGB(1,1,1);cv.setStrokeAlpha(0.07);cv.setLineWidth(0.5)
                cv.line(mx-6,8,mx-6,fh-10);cv.setStrokeAlpha(1.0)
            cv.setFont('Helvetica',5.8);cv.setFillColorRGB(0.44,0.62,0.88)
            cv.drawString(mx,fh-14,lbl)
            cv.setFont('Helvetica-Bold',7.8);cv.setFillColorRGB(*WHITE)
            cv.drawString(mx,fh-27,str(val))

        cv.restoreState()

    # ═══════════════════════════════════════════════════════
    #  INTERIOR PAGES
    # ═══════════════════════════════════════════════════════
    def draw_interior(cv,doc):
        cv.saveState()
        cv.setFillColorRGB(*NAVY);cv.rect(0,PH-TOP_MARGIN,PW,TOP_MARGIN,fill=1,stroke=0)

        # Header left gradient bar
        for i in range(TOP_MARGIN):
            f=i/TOP_MARGIN
            cv.setFillColorRGB(TEAL[0]*(1-f)+BLUE[0]*f,
                               TEAL[1]*(1-f)+BLUE[1]*f,
                               TEAL[2]*(1-f)+BLUE2[2]*f)
            cv.rect(0,PH-TOP_MARGIN+i,7,1,fill=1,stroke=0)

        # Header right gold bar
        cv.setFillColorRGB(*GOLD);cv.rect(PW-7,PH-TOP_MARGIN,7,TOP_MARGIN,fill=1,stroke=0)

        # Four-colour band at bottom of header
        seg=PW/4
        for i,hc in enumerate([TEAL,BLUE2,PURPLE,GOLD]):
            cv.setFillColorRGB(*hc);cv.rect(i*seg,PH-TOP_MARGIN,seg,3,fill=1,stroke=0)

        # Logo
        hlx=14;hly=PH-TOP_MARGIN+20
        cv.setFillColorRGB(0.04,0.20,0.52);cv.roundRect(hlx,hly,38,38,8,fill=1,stroke=0)
        cv.setStrokeColorRGB(*TEAL);cv.setLineWidth(1.0)
        cv.roundRect(hlx+2,hly+2,34,34,6,fill=0,stroke=1)
        _bone(cv,hlx+19,hly+19,sz=13,col=WHITE)

        cv.setFont('Helvetica-Bold',15);cv.setFillColorRGB(*WHITE)
        cv.drawString(hlx+46,PH-TOP_MARGIN+44,'OsteoAI')
        cv.setFont('Helvetica',7.5);cv.setFillColorRGB(0.62,0.78,0.95)
        cv.drawString(hlx+46,PH-TOP_MARGIN+30,'Bone Density Diagnostic Report  ·  Confidential')

        # Diagnosis pill in header
        pill_w=92;pill_h=16;pill_x=PW/2-pill_w/2;pill_y=PH-TOP_MARGIN+12
        cv.setFillColorRGB(*dfc);cv.setFillAlpha(0.88)
        cv.roundRect(pill_x,pill_y,pill_w,pill_h,5,fill=1,stroke=0);cv.setFillAlpha(1.0)
        cv.setFont('Helvetica-Bold',7);cv.setFillColorRGB(*WHITE)
        cv.drawCentredString(PW/2,pill_y+4,sev_s.upper())

        # Patient + page right
        cv.setFont('Helvetica-Bold',8.5);cv.setFillColorRGB(*WHITE)
        cv.drawRightString(PW-14,PH-TOP_MARGIN+46,pname)
        cv.setFont('Helvetica',7.5);cv.setFillColorRGB(0.70,0.84,0.97)
        cv.drawRightString(PW-14,PH-TOP_MARGIN+32,f'Report ID: {rid}   ·   Page {doc.page}')

        # Footer
        fh=BOT_MARGIN
        cv.setFillColorRGB(0.95,0.97,1.00);cv.rect(0,0,PW,fh,fill=1,stroke=0)
        for i,fc in enumerate([TEAL,BLUE2,PURPLE,GOLD]):
            cv.setFillColorRGB(*fc);cv.rect(i*(PW/4),fh-2,PW/4,2,fill=1,stroke=0)
        cv.setFillColorRGB(*TEAL);cv.rect(0,0,5,fh,fill=1,stroke=0)
        cv.setFillColorRGB(*GOLD);cv.rect(PW-5,0,5,fh,fill=1,stroke=0)
        cv.setFont('Helvetica',7);cv.setFillColorRGB(*MUTED)
        cv.drawString(ML,fh-16,f'Patient: {pname}   ·   {rdate}')
        cv.drawCentredString(PW/2,fh-16,'CONFIDENTIAL — For Authorised Clinical Use Only')
        cv.drawRightString(PW-ML,fh-16,f'© OsteoAI 2025   ·   {rid}')
        cv.drawCentredString(PW/2,fh-29,
            'Generated by OsteoAI AI Diagnostic System. Must be reviewed by a qualified clinician.')
        cv.restoreState()

    # Page templates
    cover_frame=Frame(0,0,PW,PH,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0,id='cover')
    interior_frame=Frame(ML,BOT_MARGIN+14,CW,PH-TOP_MARGIN-BOT_MARGIN-28,
                         leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0,id='interior')
    cover_tmpl=PT(id='Cover',frames=[cover_frame],onPage=draw_cover)
    interior_tmpl=PT(id='Interior',frames=[interior_frame],onPage=draw_interior)

    doc=BaseDocTemplate(buf,pagesize=A4,leftMargin=ML,rightMargin=MR,
        topMargin=TOP_MARGIN+14,bottomMargin=BOT_MARGIN+14,
        title='OsteoAI Diagnostic Report',author='OsteoAI Platform v3.0')
    doc.addPageTemplates([cover_tmpl,interior_tmpl])
    story=[]

    def sec(title,icon='▶',bc=BLUE):
        row=Table([[Paragraph(f'<b>{icon}  {title}</b>',sH)]],colWidths=[CW])
        row.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),_col(SILVER)),
            ('LEFTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),7),
            ('BOTTOMPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),10),
            ('LINEBELOW',(0,0),(-1,-1),3.0,_col(bc)),
            ('LINEBEFORE',(0,0),(-1,-1),4.0,_col(bc))]))
        story.append(Spacer(1,8));story.append(row)

    def tbl(data,cws,se=None):
        base=[('ROWBACKGROUNDS',(0,0),(-1,-1),[_col(WHITE),_col(SILVER)]),
              ('BOX',(0,0),(-1,-1),0.5,_col(BORDER)),
              ('INNERGRID',(0,0),(-1,-1),0.3,_col(BORDER)),
              ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
              ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
              ('VALIGN',(0,0),(-1,-1),'TOP'),
              ('LINEBEFORE',(0,0),(0,-1),2.5,_col(BLUE))]
        if se:base+=se
        t=Table(data,colWidths=cws);t.setStyle(TableStyle(base));return t

    # Cover -> Interior switch
    story.append(NextPageTemplate('Interior'))
    story.append(PageBreak())

    # ① Patient Info
    sec('PATIENT INFORMATION & CLINICAL DETAILS','①',BLUE)
    ik=[('Patient Name','Report Date'),('Age','Gender'),('BMI','T-Score'),
        ('Z-Score','Analysis Mode'),('Referring Physician','Hospital/Clinic'),('Contact','Blood Type')]
    ir=[]
    for k1,k2 in ik:
        ir.append([Paragraph(k1.upper(),sLb),Paragraph(str(patient_data.get(k1,'—')),sBV),
                   Paragraph(k2.upper(),sLb),Paragraph(str(patient_data.get(k2,'—')),sBV)])
    story.append(KeepTogether(tbl(ir,[CW*0.17,CW*0.33,CW*0.17,CW*0.33],
        se=[('BACKGROUND',(0,0),(0,-1),_col(SILVER2)),('BACKGROUND',(2,0),(2,-1),_col(SILVER2))])))

    class GaugeF(Flowable):
        def __init__(self,ts,frax,w=CW):
            Flowable.__init__(self);self.ts=ts;self.fr=frax;self.width=w;self.height=136
        def draw(self):
            cv=self.canv;w=self.width;h=self.height
            _rr(cv,0,0,w,h,8,fill=SILVER,stroke=BORDER)
            cv.setFillColorRGB(*BLUE);cv.roundRect(0,0,4,h,2,fill=1,stroke=0)
            _gauge(cv,95,72,self.ts)
            lx=178;cv.setFont('Helvetica-Bold',8.5);cv.setFillColorRGB(*NAVY)
            cv.drawString(lx,h-16,'WHO T-Score Classification')
            iy=h-34
            for col,lbl,rng in [(GREEN,'Normal','T ≥ −1.0'),(AMBER,'Osteopenia','−2.5 < T < −1.0'),(RED,'Osteoporosis','T ≤ −2.5')]:
                cv.setFillColorRGB(*col);cv.roundRect(lx,iy,10,10,2,fill=1,stroke=0)
                cv.setFont('Helvetica-Bold',8);cv.setFillColorRGB(*DARK);cv.drawString(lx+14,iy+1,lbl)
                cv.setFont('Helvetica',7.5);cv.setFillColorRGB(*MUTED);cv.drawString(lx+72,iy+1,rng)
                iy-=19
            _frax(cv,lx,8,w-lx-6,self.fr)

    story.append(Spacer(1,10));story.append(GaugeF(ts,frax_val,CW))

    # ② Diagnosis
    story.append(Spacer(1,10));sec('AI DIAGNOSIS RESULT','②',dfc)
    dd=[[Paragraph(f'<font size="20"><b>{pred.upper()}</b></font>',
                   ParagraphStyle('D1',fontName='Helvetica-Bold',fontSize=20,textColor=_col(dfc),leading=24)),
         Paragraph(f'<b>{sev}</b><br/><font name="Helvetica" size="8" color="grey">Confidence: {conf:.1f}%   ·   {rid}</font>',
                   ParagraphStyle('D2',fontName='Helvetica-Bold',fontSize=10,textColor=_col(dfc),leading=16,alignment=TA_RIGHT))]]
    dt=Table(dd,colWidths=[CW*0.50,CW*0.50])
    dt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),_col(dbg)),
        ('BOX',(0,0),(-1,-1),2.5,_col(dbd)),('LINEBEFORE',(0,0),(0,-1),6.0,_col(dfc)),
        ('LINEBELOW',(0,0),(-1,-1),2.5,_col(dfc)),
        ('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14),
        ('LEFTPADDING',(0,0),(-1,-1),16),('RIGHTPADDING',(0,0),(-1,-1),14),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(KeepTogether(dt))
    filled=CW*conf/100
    cb=Table([['','']],colWidths=[filled,max(CW-filled,0.5)],rowHeights=[7])
    cb.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),_col(dfc)),('BACKGROUND',(1,0),(1,0),_col(BORDER)),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(cb);story.append(Spacer(1,6));story.append(Paragraph(ddesc,sBy))

    # ③ Risk Factors
    rfs=patient_data.get('Risk Factors',[])
    if rfs:
        story.append(Spacer(1,6));sec('IDENTIFIED RISK FACTORS','③',ORANGE)
        rp=['<b>'+( rf[0] if isinstance(rf,(list,tuple)) else str(rf))+'</b>  ['+( rf[1] if isinstance(rf,(list,tuple)) and len(rf)>1 else 'High')+']' for rf in rfs]
        story.append(Paragraph('    ◆    '.join(rp),
            ParagraphStyle('RF',fontName='Helvetica',fontSize=8.8,textColor=_col(RED),leading=15,
                borderPad=10,backColor=_col(REDBG),borderColor=_col(REDBD),borderWidth=1.5,borderRadius=6,leftIndent=4)))

    # ④ Recommendations
    story.append(Spacer(1,6));sec('CLINICAL RECOMMENDATIONS','④',GREEN)
    if pred=='Osteoporosis':
        recs=[('Specialist Referral','Immediate referral to endocrinologist or rheumatologist. Do not delay pharmacotherapy.'),
              ('Pharmacotherapy','First-line: Alendronate 70 mg once weekly OR Risedronate 35 mg once weekly. Assess eGFR prior. Consider denosumab/teriparatide for severe cases.'),
              ('Calcium & Vitamin D','Calcium 1,200 mg/day (divided doses). Vitamin D3 800–1,000 IU/day. Supplement if dietary intake insufficient.'),
              ('Fall Prevention','Home hazard assessment; grab rails; non-slip flooring. Physiotherapy for balance and strength.'),
              ('Exercise','Low-impact weight-bearing (walking, Tai Chi). Resistance training 2×/week supervised. Avoid high-impact and spinal flexion exercises.'),
              ('DEXA Follow-up','Repeat DEXA at 12–24 months post-therapy initiation to assess treatment response.'),
              ('Lifestyle','Smoking cessation; alcohol ≤1 unit/day; adequate protein ≥1 g/kg/day; sun exposure for Vitamin D.')]
    elif pred=='Osteopenia':
        recs=[('Monitoring','Repeat DEXA in 1–2 years. Calculate 10-year FRAX probability to guide therapy decisions.'),
              ('Nutrition','Calcium 1,000 mg/day + Vitamin D3 600–800 IU/day. Dairy, leafy greens, fortified foods.'),
              ('Exercise','Weight-bearing 5×/week (brisk walking, aerobics). Resistance training 3×/week.'),
              ('Risk Modification','Smoking cessation. Alcohol reduction. Achieve/maintain healthy BMI. Review bone-depleting medications.'),
              ('Pharmacotherapy','Initiate only if FRAX 10-yr hip fracture ≥3% or major osteoporotic fracture ≥20%.'),
              ('Lifestyle','Adequate sun exposure. Protein ≥1 g/kg/day. Limit caffeine and high-sodium diet.')]
    else:
        recs=[('Screening','Routine DEXA: every 2 years from age 65 (women) / 70 (men), or earlier if risk factors present.'),
              ('Nutrition','Maintain calcium 1,000 mg/day. Vitamin D 400–600 IU/day. Balanced bone-supportive diet.'),
              ('Exercise','Continue weight-bearing ≥30 min/day. Resistance training 2–3×/week to maintain bone mass.'),
              ('Lifestyle','Avoid smoking and excessive alcohol. Maintain healthy body weight. Minimise fall risks.'),
              ('Reassurance','Bone mineral density currently normal. Reinforce preventive behaviours long-term.')]
    rr2=[[Paragraph(f'<b>{r[0]}</b>',sLb),Paragraph(r[1],sV)] for r in recs]
    story.append(KeepTogether(tbl(rr2,[CW*0.22,CW*0.78],
        se=[('BACKGROUND',(0,0),(0,-1),_col(GREENBG)),('TEXTCOLOR',(0,0),(0,-1),_col(GREEN))])))

    # ⑤ Medication Table
    story.append(Spacer(1,6));sec('MEDICATION REFERENCE TABLE','⑤',PURPLE)
    if pred=='Osteoporosis':
        meds=[['Alendronate','70 mg','Once weekly (oral)','Bisphosphonate — 1st line','Renal fn, jaw osteonecrosis'],
              ['Risedronate','35 mg','Once weekly (oral)','Bisphosphonate — 1st line','GI tolerability'],
              ['Denosumab','60 mg','Every 6 months (SC)','RANK-L inhibitor — 2nd line','Hypocalcaemia, infections'],
              ['Teriparatide','20 mcg','Daily (SC)','PTH analogue — severe cases','Osteosarcoma risk, cost'],
              ['Calcium Citrate','500 mg','Twice daily (oral)','Supplement','GI upset if >600 mg at once'],
              ['Vitamin D3','800 IU','Daily (oral)','Supplement','Toxicity >4,000 IU/day']]
    elif pred=='Osteopenia':
        meds=[['Calcium Carbonate','500 mg','Twice daily (oral)','Supplement','Take with food'],
              ['Vitamin D3','600 IU','Daily (oral)','Supplement','Rare toxicity at this dose'],
              ['Alendronate','70 mg','Weekly if FRAX≥20%','Bisphosphonate — if indicated','Renal fn, GI']]
    else:
        meds=[['Calcium','1,000 mg','Daily (dietary/suppl.)','Preventive','Balance with dietary intake'],
              ['Vitamin D3','400 IU','Daily (oral/sun)','Preventive','Monitor 25-OH Vit D annually']]
    mh=[Paragraph(h,sTg) for h in ['MEDICATION','DOSE','FREQUENCY','CLASS / INDICATION','MONITOR FOR']]
    mr=[mh]+[[Paragraph(c,sSm) for c in row] for row in meds]
    mt=Table(mr,colWidths=[CW*0.16,CW*0.09,CW*0.17,CW*0.33,CW*0.25],repeatRows=1)
    mt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),_col(NAVY)),('LINEBELOW',(0,0),(-1,0),2.5,_col(TEAL)),
        ('LINEBEFORE',(0,0),(0,-1),4.0,_col(PURPLE)),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[_col(WHITE),_col(SILVER)]),
        ('BOX',(0,0),(-1,-1),0.5,_col(BORDER)),('INNERGRID',(0,0),(-1,-1),0.3,_col(BORDER)),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('VALIGN',(0,0),(-1,-1),'TOP')]))
    story.append(KeepTogether(mt))

    # ⑥ Meal plans + exercises
    if detailed_summary:
        lines=[l.strip() for l in detailed_summary.split('\n') if l.strip()]
        sm={};cur=None
        for ln in lines:
            if ln.isupper() and len(ln)>6:cur=ln;sm[cur]=[]
            elif cur:sm[cur].append(ln)
        for pk,plbl,pcol in [('VEGETARIAN MEAL PLAN','VEGETARIAN MEAL PLAN',GREEN),
                              ('NON-VEGETARIAN MEAL PLAN','NON-VEGETARIAN MEAL PLAN',ORANGE)]:
            if pk in sm and sm[pk]:
                story.append(Spacer(1,6));sec(plbl,'⑥',pcol)
                ml2=[]
                for mln in sm[pk]:
                    if ':' in mln:
                        s2,it=mln.split(':',1)
                        ml2.append([Paragraph(s2.title(),sLb),Paragraph(it.strip(),sV)])
                if ml2:story.append(tbl(ml2,[CW*0.14,CW*0.86],
                    se=[('BACKGROUND',(0,0),(0,-1),_col(GREENBG)),('TEXTCOLOR',(0,0),(0,-1),_col(GREEN))]))
        if 'EXERCISE RECOMMENDATIONS' in sm:
            story.append(Spacer(1,6));sec('EXERCISE PRESCRIPTION','⑦',TEAL)
            ed=[[Paragraph(f'<b>Exercise {i+1}</b>',sLb),Paragraph(ex.lstrip('- '),sV)]
                for i,ex in enumerate(sm['EXERCISE RECOMMENDATIONS'])]
            if ed:story.append(tbl(ed,[CW*0.14,CW*0.86],
                se=[('BACKGROUND',(0,0),(0,-1),_col((0.90,0.98,0.98))),('TEXTCOLOR',(0,0),(0,-1),_col(TEAL2))]))

    # ⑧ Imaging
    if image_path:
        imgs=image_path if isinstance(image_path,list) else [image_path]
        valid=[im for im in imgs if isinstance(im,dict) and os.path.exists(im.get('path',''))]
        if valid:
            story.append(PageBreak());sec('IMAGING & GRAD-CAM HEATMAP ANALYSIS','⑧',CYAN)
            story.append(Paragraph('X-ray processed by CNN module. Grad-CAM highlights anatomical regions of interest — warm zones indicate reduced bone density. Correlate findings clinically.',sBy))
            story.append(Spacer(1,10))
            iw=(CW-16)/2;ih=iw*0.78
            for pair in [valid[i:i+2] for i in range(0,len(valid),2)]:
                while len(pair)<2:pair.append(None)
                ir2,cr=[],[]
                for im in pair:
                    if im:
                        try:ir2.append(RLImage(im['path'],width=iw,height=ih));cr.append(Paragraph(im.get('caption',''),sCp))
                        except:ir2.append(Paragraph('Image unavailable',sCp));cr.append(Paragraph('',sCp))
                    else:ir2.append('');cr.append('')
                it2=Table([[ir2[0],Spacer(16,1),ir2[1]],[cr[0],'',cr[1]]],colWidths=[iw,16,iw])
                it2.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                    ('BOX',(0,0),(0,0),1.0,_col(BORDER)),('BOX',(2,0),(2,0),1.0,_col(BORDER)),
                    ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
                    ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
                story.append(it2);story.append(Spacer(1,10))

    # ⑨ Sign-off
    story.append(Spacer(1,12));sec('CLINICIAN REVIEW & SIGN-OFF','⑨',GOLD)
    phy=patient_data.get('Referring Physician','____________________________')
    hos=patient_data.get('Hospital/Clinic','____________________________')
    sr=[[Paragraph('REVIEWED BY',sLb),Paragraph(phy,sBV),Paragraph('HOSPITAL/CLINIC',sLb),Paragraph(hos,sBV)],
        [Paragraph('DATE OF REVIEW',sLb),Paragraph('____________________',sV),Paragraph('SIGNATURE',sLb),Paragraph('_________________________',sV)],
        [Paragraph('CLINICAL NOTES',sLb),Paragraph('_______________________________________',sV),Paragraph('FOLLOW-UP DATE',sLb),Paragraph('____________________',sV)]]
    story.append(KeepTogether(tbl(sr,[CW*0.17,CW*0.33,CW*0.17,CW*0.33],
        se=[('BACKGROUND',(0,0),(0,-1),_col(SILVER2)),('BACKGROUND',(2,0),(2,-1),_col(SILVER2)),
            ('LINEBEFORE',(0,0),(0,-1),4.0,_col(GOLD))])))

    story.append(Spacer(1,16))
    story.append(HRFlowable(width='100%',thickness=0.5,color=_col(BORDER),spaceAfter=6))
    story.append(Paragraph('<b>Legal Disclaimer:</b> This report was generated by the OsteoAI Artificial Intelligence Diagnostic System (v3.0) and is provided solely as a clinical decision-support aid. It does <b>NOT</b> constitute an independent medical diagnosis. All findings must be reviewed, validated, and actioned by a licensed healthcare professional. FRAX estimates are simplified approximations and should not replace the official WHO FRAX tool. OsteoAI accepts no liability for clinical decisions made solely on the basis of this report.',sDi))

    doc.build(story)
    return buf.getvalue()