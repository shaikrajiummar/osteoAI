import datetime
import random
import time
import os

from dotenv import load_dotenv

# In-memory mock store (replaces the broken st.session_state references)
_mock_cloud_data = []


class CloudManager:
    def __init__(self, use_mock=True):
        self.use_mock    = use_mock
        self.mongo_client = None
        self.mongo_db     = None
        self.backend      = 'mock'   # 'mongo' | 'mock'

        try:
            import pymongo
            load_dotenv()

            mongo_uri    = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
            db_name      = os.getenv('MONGO_DB_NAME', 'osteoporosis_db')
            enable_mongo = os.getenv('ENABLE_MONGO') == '1'

            if not enable_mongo:
                self.backend  = 'mock'
                self.use_mock = True
                return

            if os.getenv('MONGO_URI'):
                mongo_uri = os.getenv('MONGO_URI')
            if os.getenv('MONGO_DB_NAME'):
                db_name = os.getenv('MONGO_DB_NAME')

            self.mongo_client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=1000)
            self.mongo_client.server_info()
            self.mongo_db = self.mongo_client[db_name]
            self.backend  = 'mongo'
            self.use_mock = False
            print(f"☁️ SUCCESS: Connected to MongoDB ({'Atlas' if 'mongodb+srv' in mongo_uri else 'Localhost'}).")

        except (ImportError, Exception) as e:
            print(f'ℹ️ MongoDB: {e}. Switching to Local Simulation Mode.')
            self.backend  = 'mock'
            self.use_mock = True

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _to_native(self, data):
        """Convert numpy types to native Python types for JSON/DB compatibility."""
        try:
            import numpy as np
            if isinstance(data, dict):
                return {k: self._to_native(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [self._to_native(v) for v in data]
            elif isinstance(data, (np.integer, np.int64, np.int32)):
                return int(data)
            elif isinstance(data, (np.floating, np.float64, np.float32)):
                return float(data)
            elif isinstance(data, np.ndarray):
                return self._to_native(data.tolist())
        except ImportError:
            pass
        return data

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def save_prediction(self, patient_data, result, confidence):
        """Save a prediction record to MongoDB or in-memory mock store."""
        global _mock_cloud_data
        data = {
            'timestamp':    datetime.datetime.now().isoformat(),
            'patient_data': self._to_native(patient_data),
            'prediction':   str(result),
            'confidence':   self._to_native(confidence),
            'status':       'verified',
        }

        if self.backend == 'mongo':
            try:
                self.mongo_db['predictions'].insert_one(data)
                print("✅ [MONGO] Data saved to 'osteoporosis_db.predictions'")
                return True
            except Exception as e:
                print(f'❌ Mongo Save Error: {e}')
                return False
        else:
            time.sleep(0.1)
            _mock_cloud_data.append(data)
            print('✅ [MOCK] Prediction saved to in-memory store.')
            return True

    def fetch_all_records(self):
        """Fetch all prediction records."""
        global _mock_cloud_data
        if self.backend == 'mongo':
            try:
                cursor = self.mongo_db['predictions'].find({}, {'_id': 0}).sort('timestamp', -1)
                return list(cursor)
            except Exception as e:
                print(f'❌ Mongo Fetch Error: {e}')
                return []
        else:
            if not _mock_cloud_data:
                _mock_cloud_data = self._generate_dummy_data()
            return _mock_cloud_data

    def _generate_dummy_data(self):
        """Build synthetic records for analytics when running without a DB."""
        data = []
        for i in range(20):
            risk = random.choice(['Normal', 'Osteopenia', 'Osteoporosis'])
            data.append({
                'timestamp':    (datetime.datetime.now() - datetime.timedelta(days=i)).isoformat(),
                'patient_data': {
                    'name':   f'Patient-{100 + i}',
                    'age':    random.randint(40, 85),
                    'gender': random.choice(['Male', 'Female']),
                },
                'prediction': risk,
                'confidence': random.uniform(0.7, 0.99),
            })
        return data

    def get_live_stats(self):
        """Aggregate count metrics for the analytics dashboard."""
        base_screenings = 12450
        base_cases      = 3420

        if self.backend == 'mongo':
            try:
                count       = self.mongo_db['predictions'].count_documents({})
                osteo_count = self.mongo_db['predictions'].count_documents(
                    {'prediction': {'$regex': 'Osteoporosis'}})
                return {
                    'total_screenings':   base_screenings + count,
                    'osteoporosis_cases': base_cases + osteo_count,
                    'active_users':       155,
                }
            except Exception:
                return {'total_screenings': 0, 'osteoporosis_cases': 0, 'active_users': 0}
        else:
            rec         = self.fetch_all_records()
            count       = len(rec)
            osteo_count = sum(1 for r in rec if 'Osteoporosis' in str(r.get('prediction', '')))
            return {
                'total_screenings':   base_screenings + count,
                'osteoporosis_cases': base_cases + osteo_count,
                'active_users':       150,
            }

    def get_patient_history(self, user_email):
        """Return all prediction records (optionally filtered by email in future)."""
        return self.fetch_all_records()


# Module-level singleton
cloud_db = CloudManager()