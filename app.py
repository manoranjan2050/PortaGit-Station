import os
import sys
import platform
import subprocess
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
import git
import requests
import time
import threading
import tkinter as tk
from tkinter import filedialog
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# --- Security Hardening: Unique Secret Key ---
def get_secret_key():
    key = os.environ.get('SECRET_KEY')
    if not key:
        # Generate a random key if not exists in .env
        import secrets
        key = secrets.token_hex(32)
        with open('.env', 'a') as f:
            f.write(f"\nSECRET_KEY={key}")
    return key

app.secret_key = get_secret_key()

# Login Manager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_DATA_PATH'] = os.path.join(basedir, 'data')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data', 'git_dashboard.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure data directory exists
if not os.path.exists(os.path.join(basedir, 'data')):
    os.makedirs(os.path.join(basedir, 'data'))

db = SQLAlchemy(app)

# --- Encryption Helpers ---
KEY_FILE = os.path.join(basedir, 'data', 'secret.key')

def get_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
    with open(KEY_FILE, 'rb') as f:
        return f.read()

def encrypt_token(token):
    f = Fernet(get_key())
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token):
    f = Fernet(get_key())
    return f.decrypt(encrypted_token.encode()).decode()

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    theme = db.Column(db.String(20), default='light') # light, dark
    accent_color = db.Column(db.String(20), default='blue')
    accounts = db.relationship('Account', backref='user', lazy=True)
    repos = db.relationship('Repository', backref='user', lazy=True)
    logs = db.relationship('ActivityLog', backref='user', lazy=True)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    github_user = db.Column(db.String(100), nullable=False)
    token = db.Column(db.Text, nullable=False)  # Encrypted
    is_active = db.Column(db.Boolean, default=False)

class Repository(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    local_path = db.Column(db.String(255), nullable=False)
    remote_url = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(50), nullable=True, default='General')
    run_command = db.Column(db.String(255), nullable=True)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    action = db.Column(db.String(255), nullable=False)
    repo_name = db.Column(db.String(100), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Logging Helper ---
def add_log(action, repo_name=None):
    log = ActivityLog(user_id=current_user.id, action=action, repo_name=repo_name)
    db.session.add(log)
    db.session.commit()

# --- Cross-Platform Helpers ---
def open_path_native(path):
    try:
        if platform.system() == 'Windows':
            os.startfile(path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', path])
        else:  # Linux
            subprocess.run(['xdg-open', path])
        return True
    except Exception as e:
        print(f"Error opening path: {e}")
        return False

def run_command_native(command, cwd):
    if platform.system() == 'Windows':
        os.chdir(cwd)
        os.system(f'start cmd /k "{command}"')
    elif platform.system() == 'Darwin':  # macOS
        # Opens terminal, cd to dir, and run command
        subprocess.run(['osascript', '-e', f'tell application "Terminal" to do script "cd {cwd} && {command}"'])
    else:  # Linux (tries gnome-terminal or xterm)
        try:
            subprocess.run(['gnome-terminal', '--working-directory', cwd, '--', 'bash', '-c', f'{command}; exec bash'])
        except:
            subprocess.run(['xterm', '-e', f'cd {cwd} && {command}'])

# Create tables
with app.app_context():
    db.create_all()

# --- Auth Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
        else:
            hashed_pw = generate_password_hash(password)
            new_user = User(username=username, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            flash('Account created! Please log in.')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/settings/theme', methods=['POST'])
@login_required
def update_theme():
    current_user.theme = request.form.get('theme')
    current_user.accent_color = request.form.get('accent_color', 'blue')
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.context_processor
def inject_accounts():
    if current_user.is_authenticated:
        return {
            'all_accounts': Account.query.filter_by(user_id=current_user.id).all(),
            'active_account': Account.query.filter_by(user_id=current_user.id, is_active=True).first()
        }
    return {'all_accounts': [], 'active_account': None}

# --- Routes ---
@app.route('/utils/browse-folder')
@login_required
def browse_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder_selected = filedialog.askdirectory()
    root.destroy()
    return {'path': folder_selected}

@app.route('/')
@login_required
def index():
    active_account = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    categories = db.session.query(Repository.category, db.func.count(Repository.id)).filter_by(user_id=current_user.id).group_by(Repository.category).all()
    return render_template('index.html', active_account=active_account, repos=repos, categories=categories)

# --- Device Flow State ---
device_flows = {}

@app.route('/accounts/device-login', methods=['POST'])
@login_required
def device_login():
    client_id = request.form.get('client_id')
    if not client_id:
        flash("Please provide a Client ID.")
        return redirect(url_for('accounts'))
    try:
        response = requests.post('https://github.com/login/device/code', data={'client_id': client_id, 'scope': 'repo,user'}, headers={'Accept': 'application/json'})
        data = response.json()
        if 'device_code' in data:
            flow_id = data['device_code']
            device_flows[flow_id] = {'user_id': current_user.id, 'client_id': client_id, 'user_code': data['user_code'], 'verification_uri': data['verification_uri'], 'expires_in': data['expires_in'], 'interval': data['interval']}
            return render_template('device_auth.html', flow=device_flows[flow_id], flow_id=flow_id)
        else:
            flash(f"Error: {data.get('error_description', 'Unknown error')}")
            return redirect(url_for('accounts'))
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect(url_for('accounts'))

@app.route('/accounts/device-check/<flow_id>')
@login_required
def device_check(flow_id):
    flow = device_flows.get(flow_id)
    if not flow or flow['user_id'] != current_user.id: return {'status': 'error'}
    try:
        response = requests.post('https://github.com/login/oauth/access_token', data={'client_id': flow['client_id'], 'device_code': flow_id, 'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'}, headers={'Accept': 'application/json'})
        data = response.json()
        if 'access_token' in data:
            token = data['access_token']
            user_data = requests.get('https://api.github.com/user', headers={'Authorization': f'token {token}'}).json()
            github_user = user_data.get('login')
            email = user_data.get('email') or f"{github_user}@users.noreply.github.com"
            new_account = Account(user_id=current_user.id, name=f"GitHub ({github_user})", github_user=github_user, email=email, token=encrypt_token(token), is_active=(Account.query.filter_by(user_id=current_user.id).count() == 0))
            db.session.add(new_account)
            db.session.commit()
            del device_flows[flow_id]
            return {'status': 'success', 'message': f"Account added!"}
        elif data.get('error') == 'authorization_pending': return {'status': 'pending'}
        else: return {'status': 'error', 'message': data.get('error_description', 'Failed')}
    except Exception as e: return {'status': 'error', 'message': str(e)}

@app.route('/accounts/oauth-login', methods=['POST'])
@login_required
def oauth_login():
    client_id = request.form.get('client_id')
    client_secret = request.form.get('client_secret')
    if not client_id or not client_secret: return redirect(url_for('accounts'))
    session['oauth_client_id'] = client_id
    session['oauth_client_secret'] = client_secret
    return redirect(f"https://github.com/login/oauth/authorize?client_id={client_id}&scope=repo,user")

@app.route('/callback')
@login_required
def oauth_callback():
    code = request.args.get('code')
    cid = session.get('oauth_client_id')
    sec = session.get('oauth_client_secret')
    try:
        data = requests.post('https://github.com/login/oauth/access_token', data={'client_id': cid, 'client_secret': sec, 'code': code}, headers={'Accept': 'application/json'}).json()
        if 'access_token' in data:
            token = data['access_token']
            user_data = requests.get('https://api.github.com/user', headers={'Authorization': f'token {token}'}).json()
            github_user = user_data.get('login')
            new_account = Account(user_id=current_user.id, name=f"GitHub ({github_user})", github_user=github_user, email=user_data.get('email') or f"{github_user}@users.noreply.github.com", token=encrypt_token(token), is_active=(Account.query.filter_by(user_id=current_user.id).count() == 0))
            db.session.add(new_account)
            db.session.commit()
            flash(f"Account added!")
    except Exception as e: flash(f"Error: {str(e)}")
    return redirect(url_for('accounts'))

@app.route('/accounts/check/<int:id>', methods=['POST'])
@login_required
def check_account(id):
    account = Account.query.filter_by(user_id=current_user.id, id=id).first()
    if not account: return redirect(url_for('accounts'))
    try:
        response = requests.get('https://api.github.com/user/repos?per_page=1', headers={'Authorization': f'token {decrypt_token(account.token)}'})
        if response.status_code == 200: flash("Connection Successful!")
        else: flash("Connection Failed.")
    except Exception as e: flash(f"Error: {str(e)}")
    return redirect(url_for('accounts'))

@app.route('/github-browser')
@login_required
def github_browser():
    active_account = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not active_account: 
        flash("Please activate a GitHub account first.")
        return redirect(url_for('accounts'))
    
    remote_repos = []
    local_urls = {}
    error_msg = None
    
    try:
        response = requests.get(
            'https://api.github.com/user/repos?sort=updated&per_page=100', 
            headers={'Authorization': f'token {decrypt_token(active_account.token)}'}
        )
        data = response.json()
        
        if isinstance(data, list):
            remote_repos = data
        else:
            error_msg = data.get('message', 'Could not fetch repositories.')
            flash(f"GitHub API Error: {error_msg}")
            
        # Get local repo remote URLs for comparison
        local_repos = Repository.query.filter_by(user_id=current_user.id).all()
        local_urls = {r.remote_url: r.id for r in local_repos if r.remote_url}
        
    except Exception as e: 
        flash(f"Error connecting to GitHub: {str(e)}")
        
    return render_template('github_browser.html', remote_repos=remote_repos, local_urls=local_urls)

@app.route('/repositories/edit/<int:id>')
@login_required
def edit_repository_files(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    if not repo_data: return redirect(url_for('repositories'))
    rel_path = request.args.get('path', '')
    full_path = os.path.join(repo_data.local_path, rel_path)
    if os.path.isdir(full_path):
        files = [{'name': item, 'path': os.path.join(rel_path, item), 'is_dir': os.path.isdir(os.path.join(full_path, item))} for item in os.listdir(full_path) if item != '.git']
        return render_template('repo_editor_list.html', repo=repo_data, files=files, current_path=rel_path)
    else:
        try:
            with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
            return render_template('repo_editor_file.html', repo=repo_data, path=rel_path, content=content)
        except: return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/save/<int:id>', methods=['POST'])
@login_required
def save_repository_file(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    rel_path = request.form.get('path')
    content = request.form.get('content')
    try:
        with open(os.path.join(repo_data.local_path, rel_path), 'w', encoding='utf-8') as f: f.write(content)
        flash("Saved.")
    except: flash("Error.")
    return redirect(url_for('edit_repository_files', id=id, path=rel_path))

@app.route('/accounts')
@login_required
def accounts():
    all_accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('accounts.html', accounts=all_accounts)

@app.route('/accounts/add', methods=['POST'])
@login_required
def add_account():
    name, guser, email, token = request.form.get('name'), request.form.get('github_user'), request.form.get('email'), request.form.get('token')
    new_account = Account(user_id=current_user.id, name=name, github_user=guser, email=email, token=encrypt_token(token), is_active=(Account.query.filter_by(user_id=current_user.id).count() == 0))
    db.session.add(new_account)
    db.session.commit()
    flash("Account added.")
    return redirect(url_for('accounts'))

@app.route('/accounts/activate/<int:id>', methods=['POST'])
@login_required
def activate_account(id):
    Account.query.filter_by(user_id=current_user.id).update({Account.is_active: False})
    account = Account.query.filter_by(user_id=current_user.id, id=id).first()
    if account:
        account.is_active = True
        db.session.commit()
    return redirect(request.referrer or url_for('accounts'))

@app.route('/repositories')
@login_required
def repositories():
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    return render_template('repositories.html', repos=repos)

@app.route('/repositories/add', methods=['POST'])
@login_required
def add_repository():
    name, lpath = request.form.get('name'), request.form.get('local_path')
    remote_url = request.form.get('remote_url')
    
    # 1. Check if folder exists
    if not os.path.exists(lpath):
        flash(f"Error: Folder '{lpath}' does not exist.")
        return redirect(url_for('repositories'))
        
    try:
        # 2. Handle Git initialization or remote setup
        repo = None
        if not os.path.exists(os.path.join(lpath, '.git')):
            # Offer to init if not a repo
            repo = git.Repo.init(lpath)
            add_log("Initialized new Git repository", name)
        else:
            repo = git.Repo(lpath)
            
        # 3. Handle Remote URL linking
        if remote_url:
            # If no remote named 'origin' exists, create it
            if 'origin' not in [r.name for r in repo.remotes]:
                repo.create_remote('origin', remote_url)
                add_log(f"Linked to remote: {remote_url}", name)
            else:
                # Update existing origin URL if it's different
                repo.remotes.origin.set_url(remote_url)
        else:
            # Try to auto-detect remote URL if not provided
            try: remote_url = repo.remotes.origin.url
            except: pass
            
        new_repo = Repository(user_id=current_user.id, name=name, local_path=lpath, remote_url=remote_url)
        db.session.add(new_repo)
        db.session.commit()
        flash(f"Repository '{name}' added and configured!")
    except Exception as e:
        flash(f"Setup Error: {str(e)}")
        
    return redirect(url_for('repositories'))

@app.route('/repositories/edit-meta/<int:id>', methods=['POST'])
@login_required
def edit_repository_meta(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    if repo_data:
        repo_data.name, repo_data.local_path = request.form.get('name'), request.form.get('local_path')
        repo_data.category, repo_data.run_command = request.form.get('category', 'General'), request.form.get('run_command')
        db.session.commit()
    return redirect(url_for('repositories'))

@app.route('/repositories/create', methods=['POST'])
@login_required
def create_repository():
    name, pdir, desc = request.form.get('name'), request.form.get('parent_dir'), request.form.get('description', '')
    acc = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not acc: return redirect(url_for('repositories'))
    try:
        token = decrypt_token(acc.token)
        res = requests.post('https://api.github.com/user/repos', json={'name': name, 'description': desc, 'private': request.form.get('private') == 'on'}, headers={'Authorization': f'token {token}'}).json()
        local_path = os.path.join(pdir, name)
        os.makedirs(local_path)
        repo = git.Repo.init(local_path)
        with open(os.path.join(local_path, 'README.md'), 'w') as f: f.write(f"# {name}")
        with repo.config_writer() as cw:
            cw.set_value("user", "name", acc.github_user)
            cw.set_value("user", "email", acc.email)
        repo.index.add(['README.md']); repo.index.commit("Initial commit")
        origin = repo.create_remote('origin', res['clone_url'])
        origin.set_url(get_authenticated_url(res['clone_url'], acc.github_user, token))
        repo.git.branch('-M', 'main'); origin.push('main'); origin.set_url(res['clone_url'])
        db.session.add(Repository(user_id=current_user.id, name=name, local_path=local_path, remote_url=res['clone_url']))
        db.session.commit()
    except Exception as e: flash(f"Error: {str(e)}")
    return redirect(url_for('repositories'))

@app.route('/repositories/clone', methods=['POST'])
@login_required
def clone_repository():
    url, pdir = request.form.get('url'), request.form.get('parent_dir')
    fname = request.form.get('folder_name') or url.split('/')[-1].replace('.git', '')
    acc = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not acc: return redirect(url_for('repositories'))
    try:
        local_path = os.path.join(pdir, fname)
        git.Repo.clone_from(get_authenticated_url(url, acc.github_user, decrypt_token(acc.token)), local_path)
        db.session.add(Repository(user_id=current_user.id, name=fname, local_path=local_path, remote_url=url))
        db.session.commit()
    except Exception as e: flash(f"Error: {str(e)}")
    return redirect(url_for('repositories'))

@app.route('/repositories/open/<int:id>')
@login_required
def open_repository_folder(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    if repo_data:
        if os.path.exists(repo_data.local_path):
            if open_path_native(repo_data.local_path):
                flash(f"Opened folder: {repo_data.local_path}")
            else:
                flash(f"Failed to open folder: {repo_data.local_path}")
        else:
            flash(f"Error: Path does not exist: {repo_data.local_path}")
    return redirect(url_for('repositories'))

@app.route('/repositories/manage/<int:id>')
@login_required
def manage_repository(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    if not repo_data: return redirect(url_for('repositories'))
    try:
        repo = git.Repo(repo_data.local_path)
        
        # Safe way to get branch name
        active_branch_name = "Unknown"
        is_detached = False
        try:
            active_branch_name = repo.active_branch.name
        except TypeError:
            try:
                active_branch_name = f"Detached: {repo.head.commit.hexsha[:7]}"
                is_detached = True
            except:
                active_branch_name = "Detached"
                is_detached = True
        except:
            active_branch_name = "No Branch"

        ahead = behind = 0
        if not is_detached:
            try:
                active_branch = repo.active_branch
                if active_branch.tracking_branch():
                    ahead = sum(1 for c in repo.iter_commits(f'{active_branch.tracking_branch().name}..{active_branch.name}'))
                    behind = sum(1 for c in repo.iter_commits(f'{active_branch.name}..{active_branch.tracking_branch().name}'))
            except: pass

        # Check if HEAD exists for diff and commits
        has_commits = False
        try:
            repo.head.commit
            has_commits = True
        except:
            pass

        staged_files = []
        if has_commits:
            try:
                staged_files = [item.a_path for item in repo.index.diff("HEAD")]
            except:
                pass
        else:
            # For empty repo, use git command directly to see what's staged
            try:
                staged_files = repo.git.diff('--cached', name_only=True).splitlines()
            except:
                pass

        status = {
            'branch': active_branch_name, 
            'branches': [b.name for b in repo.branches], 
            'is_dirty': repo.is_dirty() or len(repo.untracked_files) > 0, 
            'staged_files': staged_files, 
            'unstaged_files': [item.a_path for item in repo.index.diff(None)], 
            'untracked_files': repo.untracked_files, 
            'ahead': ahead, 
            'behind': behind, 
            'recent_commits': []
        }
        
        if has_commits:
            try:
                for commit in repo.iter_commits(max_count=5):
                    status['recent_commits'].append({'summary': commit.summary, 'author_name': commit.author.name, 'date': commit.authored_datetime.strftime('%Y-%m-%d %H:%M')})
            except: pass
            
        return render_template('repo_manage.html', repo=repo_data, status=status)
    except Exception as e: flash(f"Error: {str(e)}"); return redirect(url_for('repositories'))

@app.route('/repositories/fetch/<int:id>', methods=['POST'])
@login_required
def fetch_repository(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    acc = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    try:
        repo = git.Repo(repo_data.local_path)
        origin = repo.remotes.origin; old_url = origin.url
        origin.set_url(get_authenticated_url(repo_data.remote_url, acc.github_user, decrypt_token(acc.token)))
        try: origin.fetch()
        finally: origin.set_url(old_url)
    except: pass
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/history/<int:id>')
@login_required
def repository_history(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    try:
        repo = git.Repo(repo_data.local_path)
        commits = []
        try:
            # Check if HEAD exists before iterating
            repo.head.commit
            commits = [{'hexsha': c.hexsha, 'summary': c.summary, 'author_name': c.author.name, 'date': c.authored_datetime.strftime('%Y-%m-%d %H:%M'), 'message': c.message} for c in repo.iter_commits(max_count=50)]
        except:
            pass
        return render_template('repo_history.html', repo=repo_data, commits=commits)
    except: return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/tag/<int:id>', methods=['POST'])
@login_required
def create_tag(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    try: git.Repo(repo_data.local_path).create_tag(request.form.get('tag_name'), message=request.form.get('tag_message', ''))
    except: pass
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/sync-all', methods=['POST'])
@login_required
def sync_all():
    acc = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not acc: return redirect(url_for('repositories'))
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    token = decrypt_token(acc.token)
    for r in repos:
        try:
            repo = git.Repo(r.local_path)
            if repo.remotes:
                origin = repo.remotes.origin; old_url = origin.url
                origin.set_url(get_authenticated_url(r.remote_url, acc.github_user, token))
                try: origin.fetch(); repo.git.pull()
                finally: origin.set_url(old_url)
        except: continue
    return redirect(url_for('repositories'))

@app.route('/repositories/diff/<int:id>')
@login_required
def get_diff(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    try:
        repo = git.Repo(repo_data.local_path)
        path = request.args.get('path')
        return {'diff': repo.git.diff(path) or repo.git.diff('--cached', path)}
    except Exception as e: return {'error': str(e)}

@app.route('/repositories/stash/<int:id>', methods=['POST'])
@login_required
def stash_changes(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    try: git.Repo(repo_data.local_path).git.stash('save', request.form.get('message', 'Dashboard Stash'))
    except: pass
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/stash-pop/<int:id>', methods=['POST'])
@login_required
def stash_pop(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    try: git.Repo(repo_data.local_path).git.stash('pop')
    except: pass
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/run/<int:id>', methods=['POST'])
@login_required
def run_project(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    if repo_data.run_command:
        os.chdir(repo_data.local_path)
        os.system(f'start cmd /k "{repo_data.run_command}"')
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/checkout/<int:id>', methods=['POST'])
@login_required
def checkout_branch(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    try: git.Repo(repo_data.local_path).git.checkout(request.form.get('branch_name'))
    except: pass
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/create-branch/<int:id>', methods=['POST'])
@login_required
def create_branch(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    try: git.Repo(repo_data.local_path).git.checkout('-b', request.form.get('branch_name'))
    except: pass
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/delete-branch/<int:id>', methods=['POST'])
@login_required
def delete_branch(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    try: git.Repo(repo_data.local_path).delete_head(request.form.get('branch_name'))
    except: pass
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/stage/<int:id>', methods=['POST'])
@login_required
def stage_file(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    paths = request.form.getlist('file_paths')
    try:
        repo = git.Repo(repo_data.local_path)
        if '.' in paths: repo.git.add(A=True)
        else: repo.git.add(paths)
    except: pass
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/unstage/<int:id>', methods=['POST'])
@login_required
def unstage_file(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    paths = request.form.getlist('file_paths')
    try:
        repo = git.Repo(repo_data.local_path)
        # Check if HEAD exists
        try:
            repo.head.commit
            repo.git.reset('HEAD', paths)
        except:
            # For empty repo, unstage by removing from index
            repo.git.rm('--cached', paths)
    except: pass
    return redirect(url_for('manage_repository', id=id))

@app.route('/repositories/commit/<int:id>', methods=['POST'])
@login_required
def commit_repository(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    acc = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not acc: return redirect(url_for('manage_repository', id=id))
    try:
        repo = git.Repo(repo_data.local_path)
        with repo.config_writer() as cw:
            cw.set_value("user", "name", acc.github_user); cw.set_value("user", "email", acc.email)
        
        # Check if anything is already staged
        staged_files = repo.index.diff("HEAD") if repo.heads else repo.git.diff('--cached', name_only=True).splitlines()
        
        # If nothing is staged, auto-stage all (legacy behavior/convenience)
        if not staged_files:
            repo.git.add(A=True)
            
        repo.index.commit(request.form.get('message'))
        flash("Committed successfully.")
        
        if request.form.get('push') == 'true':
            token = decrypt_token(acc.token); origin = repo.remotes.origin; old_url = origin.url
            origin.set_url(get_authenticated_url(repo_data.remote_url, acc.github_user, token))
            try: 
                repo.git.push('--set-upstream', 'origin', repo.active_branch.name)
                flash("Pushed successfully.")
            finally: origin.set_url(old_url)
    except Exception as e: flash(f"Error: {str(e)}")
    return redirect(url_for('manage_repository', id=id))

def get_authenticated_url(url, user, token):
    if not url or 'github.com' not in url: return url
    if '@' in url: url = 'https://' + url.split('@')[-1]
    return url.replace('https://', f'https://{user}:{token}@')

@app.route('/repositories/push/<int:id>', methods=['POST'])
@login_required
def push_repository(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    acc = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not acc: return jsonify({'error': 'No active account'})
    try:
        repo = git.Repo(repo_data.local_path); token = decrypt_token(acc.token); origin = repo.remotes.origin; old_url = origin.url
        origin.set_url(get_authenticated_url(repo_data.remote_url, acc.github_user, token))
        try: 
            repo.git.push('--set-upstream', 'origin', repo.active_branch.name)
            add_log(f"Pushed to {repo.active_branch.name}", repo_data.name)
            return jsonify({'success': True, 'message': 'Pushed successfully.'})
        finally: origin.set_url(old_url)
    except Exception as e: return jsonify({'error': str(e)})

@app.route('/repositories/pull/<int:id>', methods=['POST'])
@login_required
def pull_repository(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    acc = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not acc: return jsonify({'error': 'No active account'})
    try:
        repo = git.Repo(repo_data.local_path); token = decrypt_token(acc.token); origin = repo.remotes.origin; old_url = origin.url
        origin.set_url(get_authenticated_url(repo_data.remote_url, acc.github_user, token))
        try: 
            origin.pull()
            add_log(f"Pulled from {repo.active_branch.name}", repo_data.name)
            return jsonify({'success': True, 'message': 'Pulled successfully.'})
        finally: origin.set_url(old_url)
    except Exception as e: return jsonify({'error': str(e)})

@app.route('/repositories/actions-status/<int:id>')
@login_required
def get_actions_status(id):
    repo_data = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    acc = Account.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not acc or not repo_data.remote_url or 'github.com' not in repo_data.remote_url:
        return jsonify({'status': 'none'})
    try:
        parts = repo_data.remote_url.replace('.git', '').split('/')
        owner, repo_name = parts[-2], parts[-1]
        res = requests.get(f'https://api.github.com/repos/{owner}/{repo_name}/actions/runs?per_page=1', headers={'Authorization': f'token {decrypt_token(acc.token)}'})
        runs = res.json().get('workflow_runs')
        if runs:
            return jsonify({'status': runs[0]['status'], 'conclusion': runs[0]['conclusion'], 'url': runs[0]['html_url']})
    except: pass
    return jsonify({'status': 'none'})

@app.route('/settings/backup-db')
@login_required
def backup_database():
    try:
        return send_file(os.path.join(basedir, 'data', 'git_dashboard.db'), as_attachment=True, download_name='git_dashboard_backup.db')
    except Exception as e:
        flash(f"Backup failed: {str(e)}")
        return redirect(url_for('index'))

@app.route('/logs')
@login_required
def logs():
    user_logs = ActivityLog.query.filter_by(user_id=current_user.id).order_by(ActivityLog.timestamp.desc()).limit(100).all()
    return render_template('logs.html', logs=user_logs)

@app.route('/api/activity-stats')
@login_required
def activity_stats():
    # Fetch commits from the last 12 months for the heatmap
    from datetime import timedelta
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    
    stats = {}
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    
    for r in repos:
        try:
            repo = git.Repo(r.local_path)
            # Only iterate if there are commits
            if repo.heads:
                for commit in repo.iter_commits(since=one_year_ago):
                    date_str = commit.authored_datetime.strftime('%Y-%m-%d')
                    stats[date_str] = stats.get(date_str, 0) + 1
        except: continue
        
    return jsonify(stats)

@app.route('/repositories/delete/<int:id>', methods=['POST'])
@login_required
def delete_repository(id):
    repo = Repository.query.filter_by(user_id=current_user.id, id=id).first()
    if repo:
        repo_name = repo.name
        db.session.delete(repo)
        db.session.commit()
        flash(f"Repository '{repo_name}' removed from dashboard.")
        add_log(f"Removed repository from dashboard", repo_name)
    return redirect(url_for('repositories'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
