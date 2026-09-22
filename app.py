import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecell_terminal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), default='student') # owner, admin, student
    points = db.Column(db.Float, default=100.0) 
    has_logged_in_as_admin = db.Column(db.Boolean, default=False)

    def get_rank(self):
        # The Owner dynamically inherits standard student rank metrics based on a cloaked 100 base score
        p = 100.0 if self.role == 'owner' else self.points
        if p <= 50: return 'D'
        if p <= 100: return 'C'
        if p <= 250: return 'B'
        if p <= 550: return 'A'
        if p <= 1000: return 'S'
        return 'SS'

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    points_reward = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending') 
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_user = db.relationship('User', foreign_keys=[assigned_to_id])

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(150), nullable=False)
    receiver = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- ROUTES ---
@app.route('/')
def landing():
    owner_exists = db.session.execute(db.select(User).filter_by(role='owner')).scalar() is not None
    return render_template('landing.html', owner_exists=owner_exists)

@app.route('/register', methods=['GET', 'POST'])
def register():
    owner_exists = db.session.execute(db.select(User).filter_by(role='owner')).scalar() is not None
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        become_owner = request.form.get('become_owner')

        existing_user = db.session.execute(db.select(User).filter_by(username=username)).scalar()
        if existing_user:
            flash('Terminal Error: Username node already bound.', 'danger')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)
        
        if not owner_exists and become_owner:
            new_user = User(username=username, password=hashed_pw, role='owner', points=100.0)
        else:
            new_user = User(username=username, password=hashed_pw, role='student', points=100.0)

        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Connect to access terminal.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', owner_exists=owner_exists)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        user = db.session.execute(db.select(User).filter_by(username=username)).scalar()

        if user and check_password_hash(user.password, password):
            if user.role == 'admin' and not user.has_logged_in_as_admin:
                user.points = 1000.0
                user.has_logged_in_as_admin = True
                db.session.commit()
                
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Access Denied: Invalid security key.', 'danger')

    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        recipient_name = request.form.get('recipient').strip()
        try:
            amount = float(request.form.get('amount'))
        except ValueError:
            flash('Transaction Error: Integer required.', 'danger')
            return redirect(url_for('dashboard'))

        recipient = db.session.execute(db.select(User).filter_by(username=recipient_name)).scalar()
        if not recipient:
            flash('Transaction Error: Target user node not found.', 'danger')
            return redirect(url_for('dashboard'))

        if amount <= 0:
            flash('Transaction Error: Amount must be positive.', 'danger')
            return redirect(url_for('dashboard'))

        # Standard validations bypassed for hidden Owner role
        if current_user.role == 'student':
            if recipient.role != 'student':
                flash('Security Violation: Students can only trade with Students.', 'danger')
                return redirect(url_for('dashboard'))
            if current_user.points < amount:
                flash('Transaction Error: Insufficient ledger balance.', 'danger')
                return redirect(url_for('dashboard'))
            current_user.points -= amount
            recipient.points += amount

        elif current_user.role == 'admin':
            if recipient.role != 'admin':
                flash('Security Violation: Admins can only trade with Admins.', 'danger')
                return redirect(url_for('dashboard'))
            if current_user.points < amount:
                flash('Transaction Error: Insufficient ledger balance.', 'danger')
                return redirect(url_for('dashboard'))
            current_user.points -= amount
            recipient.points += amount

        elif current_user.role == 'owner':
            # Stealth Override: Unlimited point pool capability, no personal points deduction
            recipient.points += amount

        tx = Transaction(sender=current_user.username, receiver=recipient.username, amount=f"{amount:.0f}")
        db.session.add(tx)
        db.session.commit()
        flash('Transaction committed successfully.', 'success')

    # Global lists for leaderboard layout
    all_users = db.session.execute(db.select(User).order_by(User.points.desc())).scalars().all()
    
    # Camouflaged calculation matrix for the leaderboard listing
    leaderboard_data = []
    for u in all_users:
        display_points = 100 if u.role == 'owner' else int(u.points)
        display_role = 'student' if u.role == 'owner' else u.role
        leaderboard_data.append({
            'username': u.username,
            'role': display_role,
            'points': display_points,
            'rank': u.get_rank()
        })
    
    # Sort leaderboard data based on cloaked score parameters
    leaderboard_data = sorted(leaderboard_data, key=lambda x: x['points'], reverse=True)

    history = db.session.execute(db.select(Transaction).filter((Transaction.sender == current_user.username) | (Transaction.receiver == current_user.username)).order_by(Transaction.timestamp.desc())).scalars().all()

    return render_template('dashboard.html', leaderboard_data=leaderboard_data, history=history)

@app.route('/management', methods=['GET', 'POST'])
@login_required
def management():
    if current_user.role not in ['admin', 'owner']:
        flash('Access Revoked: Administrative clearance missing.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'assign_role' and current_user.role == 'owner':
            user_id = request.form.get('user_id')
            new_role = request.form.get('role')
            target_user = db.session.get(User, user_id)
            if target_user and target_user.role != 'owner':
                target_user.role = new_role
                if new_role == 'admin':
                    target_user.has_logged_in_as_admin = False 
                db.session.commit()
                flash('User operational clearance updated.', 'success')

        elif action == 'create_task':
            title = request.form.get('title')
            points = float(request.form.get('points'))
            student_id = request.form.get('student_id')

            new_task = Task(title=title, points_reward=points, assigned_to_id=student_id)
            db.session.add(new_task)
            db.session.commit()
            flash('E-Cell milestone tracking active.', 'success')

        elif action == 'complete_task':
            task_id = request.form.get('task_id')
            task = db.session.get(Task, task_id)
            if task and task.status == 'pending':
                task.status = 'completed'
                student = db.session.get(User, task.assigned_to_id)
                student.points += task.points_reward
                
                tx = Transaction(sender=f"TASK ({current_user.username})", receiver=student.username, amount=f"+{task.points_reward:.0f}")
                db.session.add(tx)
                db.session.commit()
                flash('Milestone verified. Points credited automatically.', 'success')

        elif action == 'deduct_points':
            student_id = request.form.get('student_id')
            amount = float(request.form.get('amount'))
            reason = request.form.get('reason')
            
            student = db.session.get(User, student_id)
            if student:
                student.points = max(0.0, student.points - amount)
                tx = Transaction(sender=f"PENALTY ({current_user.username})", receiver=student.username, amount=f"-{amount:.0f} ({reason})")
                db.session.add(tx)
                db.session.commit()
                flash('Attendance restriction applied.', 'warning')

        return redirect(url_for('management'))

    all_users = db.session.execute(db.select(User).filter(User.role != 'owner')).scalars().all()
    students = db.session.execute(db.select(User).filter_by(role='student')).scalars().all()
    pending_tasks = db.session.execute(db.select(Task).filter_by(status='pending')).scalars().all()
    return render_template('management.html', all_users=all_users, students=students, pending_tasks=pending_tasks)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

# Create the database tables inside Render's context wrapper safely
with app.app_context():
    db.create_all()

# This tells the production server (Gunicorn) how to find your app instance
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
