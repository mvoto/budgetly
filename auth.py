from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User
from forms import LoginForm, RegistrationForm, ChangePasswordForm

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('home')
            flash('Welcome back!', 'success')
            return redirect(next_page)
        flash('Invalid email or password', 'error')
    return render_template('auth/login.html', title='Sign In', form=form)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data.lower())
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()

            # Import the helper function to create default categories
            from app import create_default_categories_for_user
            try:
                create_default_categories_for_user(user.id)
            except Exception as cat_error:
                print(f"Warning: Could not create default categories: {cat_error}")
                # Don't fail registration if default categories fail

            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {e}")
            if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                flash('Email already registered. Please use a different email.', 'error')
            else:
                flash('An error occurred during registration. Please try again.', 'error')
    return render_template('auth/register.html', title='Register', form=form)

@auth.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.new_password.data)
            try:
                db.session.commit()
                flash('Password updated successfully!', 'success')
                return redirect(url_for('auth.account'))
            except Exception as e:
                db.session.rollback()
                flash('An error occurred while updating your password. Please try again.', 'error')
                print(f"Password update error: {e}")
        else:
            flash('Current password is incorrect.', 'error')

    return render_template('auth/account.html', title='Account Settings', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))