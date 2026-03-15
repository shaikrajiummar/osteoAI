import datetime
import hashlib
import os
import json

from dotenv import load_dotenv

# File-based fallback user store (used when MongoDB is unavailable)
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
USER_DATA_DIR  = os.path.join(BASE_DIR, 'user_data')
USERS_FILE     = os.path.join(USER_DATA_DIR, '_users.json')
os.makedirs(USER_DATA_DIR, exist_ok=True)


def _load_file_users():
    """Load all users from the local JSON file store."""
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_file_users(users: dict):
    """Persist users dict to the local JSON file store."""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        return True
    except Exception as e:
        print(f'_save_file_users error: {e}')
        return False


class AuthManager:
    def __init__(self):
        self.mongo_client      = None
        self.mongo_db          = None
        self.users_collection  = None
        self.backend           = 'file'   # 'mongo' | 'file'

        try:
            import pymongo
            load_dotenv()

            mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
            db_name   = os.getenv('MONGO_DB_NAME', 'osteoporosis_db')

            self.mongo_client     = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.mongo_client.server_info()          # raises if unreachable
            self.mongo_db         = self.mongo_client[db_name]
            self.users_collection = self.mongo_db['users']
            self.backend          = 'mongo'
            print('✅ AuthManager: Connected to MongoDB.')
        except Exception as e:
            print(f'ℹ️  AuthManager: MongoDB unavailable ({e}). Using file-based user store.')
            self.backend = 'file'

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _make_token_bundle(self, email: str, local_id: str) -> dict:
        return {
            'idToken':      'mock_token_' + local_id,
            'email':        email,
            'refreshToken': 'mock_refresh_token',
            'expiresIn':    '3600',
            'localId':      local_id,
        }

    # ------------------------------------------------------------------ #
    #  MongoDB backend
    # ------------------------------------------------------------------ #

    def _mongo_sign_up(self, email: str, password: str) -> dict:
        if self.users_collection.find_one({'email': email}):
            return {'error': {'message': 'EMAIL_EXISTS'}}
        try:
            local_id  = hashlib.sha256(email.encode()).hexdigest()[:32]
            user_data = {
                'email':         email,
                'password_hash': self._hash_password(password),
                'created_at':    datetime.datetime.now().isoformat(),
                'localId':       local_id,
            }
            self.users_collection.insert_one(user_data)
            return self._make_token_bundle(email, local_id)
        except Exception as e:
            return {'error': {'message': str(e)}}

    def _mongo_sign_in(self, email: str, password: str) -> dict:
        user = self.users_collection.find_one({'email': email})
        if not user:
            return {'error': {'message': 'EMAIL_NOT_FOUND'}}
        if user['password_hash'] != self._hash_password(password):
            return {'error': {'message': 'INVALID_PASSWORD'}}
        return self._make_token_bundle(email, user['localId'])

    # ------------------------------------------------------------------ #
    #  File-based backend (fallback)
    # ------------------------------------------------------------------ #

    def _file_sign_up(self, email: str, password: str) -> dict:
        users = _load_file_users()
        if email in users:
            return {'error': {'message': 'EMAIL_EXISTS'}}
        local_id = hashlib.sha256(email.encode()).hexdigest()[:32]
        users[email] = {
            'email':         email,
            'password_hash': self._hash_password(password),
            'created_at':    datetime.datetime.now().isoformat(),
            'localId':       local_id,
        }
        if not _save_file_users(users):
            return {'error': {'message': 'Could not save user data. Check write permissions.'}}
        return self._make_token_bundle(email, local_id)

    def _file_sign_in(self, email: str, password: str) -> dict:
        users = _load_file_users()
        if email not in users:
            return {'error': {'message': 'EMAIL_NOT_FOUND'}}
        if users[email]['password_hash'] != self._hash_password(password):
            return {'error': {'message': 'INVALID_PASSWORD'}}
        return self._make_token_bundle(email, users[email]['localId'])

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def sign_up(self, email: str, password: str) -> dict:
        """Register a new user. Works with MongoDB or file-based store."""
        if self.backend == 'mongo':
            return self._mongo_sign_up(email, password)
        return self._file_sign_up(email, password)

    def sign_in(self, email: str, password: str) -> dict:
        """Authenticate an existing user."""
        if self.backend == 'mongo':
            return self._mongo_sign_in(email, password)
        return self._file_sign_in(email, password)

    def send_password_reset_email(self, email: str) -> dict:
        """Simulate sending a password-reset e-mail."""
        if self.backend == 'mongo':
            user = self.users_collection.find_one({'email': email})
        else:
            users = _load_file_users()
            user  = users.get(email)

        if not user:
            return {'error': {'message': 'EMAIL_NOT_FOUND'}}

        print(f'📧 [SIMULATION] Password reset email sent to {email}')
        return {'email': email}


# Module-level singleton
auth_manager = AuthManager()