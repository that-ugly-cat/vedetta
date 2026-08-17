"""Create the first admin user. Run once: python seed.py <username> <password>"""
import sys
from db import init_db, create_user
from auth import hash_password

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python seed.py <username> <password>")
        sys.exit(1)
    username, password = sys.argv[1], sys.argv[2]
    init_db()
    uid = create_user(username, hash_password(password), role="admin")
    print(f"Admin '{username}' created with id={uid}")
