from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_mysqldb import MySQL
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import shutil
import time
import psutil
from datetime import timedelta

app = Flask(__name__)

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'nas_user'
app.config['MYSQL_PASSWORD'] = 'Kiku@999'
app.config['MYSQL_DB'] = 'nas_server_db'
app.config['UPLOAD_FOLDER'] = '/home/kirankumarpannursivaji/nas_server/uploads'
app.config['BACKUP_FOLDER'] = '/home/kirankumarpannursivaji/nas_server/backup'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app.secret_key = 'Kiku999'
app.config['LOGS_PATH']='/home/kirankumarpannursivaji/nas_server/logs/server.log'

# Initialize MySQL
mysql = MySQL(app)

# Ensure upload and backup folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)

# Helper function for file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def home():
    user_id = session.get('user_id')
    if not user_id:
        flash('You need to log in first!')
        return redirect(url_for('login'))
    
    # Fetch the user's files from the database
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, filename FROM files WHERE uploaded_by = %s", (user_id,))
    files = cur.fetchall()
    cur.close()
    
    # Fetch role of the user
    cur = mysql.connection.cursor()
    cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    role = cur.fetchone()[0]  # Extract the role from the result
    cur.close()

    # Log the files to check if the query works
    print(f"Files for user {user_id}: {files}")
    
    return render_template('home.html', files=files, role=role)

@app.route('/manage_users', methods=['GET', 'POST'])
def manage_users():
    if session.get('role') != 'admin':
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('home'))

    # Handle user creation
    if request.method == 'POST' and 'create_user' in request.form:
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                        (username, email, password, role))
            mysql.connection.commit()
            flash('User created successfully!', 'success')
        except Exception as e:
            flash(f'Error creating user: {e}', 'error')
        finally:
            cur.close()
        return redirect(url_for('manage_users'))

    # Fetch existing users
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, email, role FROM users")
    users = cur.fetchall()
    cur.close()

    return render_template('manage_users.html', users=users)



@app.route('/delete_user', methods=['POST'])
def delete_user():
    if session.get('role') != 'admin':
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('manage_users'))

    user_id = request.form['user_id']
    
    cur = mysql.connection.cursor()
    try:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        mysql.connection.commit()
        flash('User deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting user: {e}', 'error')
    finally:
        cur.close()
    
    return redirect(url_for('manage_users'))

@app.route('/create_folder', methods=['GET', 'POST'])
def create_folder():
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        folder_name = request.form['folder_name']
        if folder_name:
            folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)  # Adjust for the folder path

            try:
                # Create the folder
                os.makedirs(folder_path, exist_ok=True)
                flash(f'Folder "{folder_name}" created successfully!', 'success')
            except Exception as e:
                flash(f'Error creating folder: {e}', 'error')
            return redirect(url_for('home'))  # Redirect to home after folder creation

    return render_template('create_folder.html')  # A new HTML page for creating folders


# Admin: View Logs
@app.route('/admin/view_logs')
def view_logs():
    # Ensure only admins can access this route
    if session.get('role') != 'admin':
        flash('You do not have permission to view this page.', 'error')
        return redirect(url_for('home'))

    # Assuming you have logs saved in a specific file
    try:
        with open(app.config['LOGS_PATH'], "r") as f:
            logs = f.readlines()
    except Exception as e:
        flash(f'Error reading logs: {e}', 'error')
        logs = []

    return render_template('view_logs.html', logs=logs)


# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                        (username, email, password, role))
            mysql.connection.commit()
            flash('User registered successfully!', 'success')
        except Exception as e:
            flash(f'Registration error: {e}', 'error')
        finally:
            cur.close()
        return redirect(url_for('login'))
    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['username'] = user[1]  # Set the username in the session
            session['role'] = user[4]
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('login.html')

# Upload route
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No file selected', 'error')
        elif not allowed_file(file.filename):
            flash('Invalid file format', 'error')
        else:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            user_id = session['user_id']
            cur = mysql.connection.cursor()
            try:
                cur.execute("INSERT INTO files (filename, filepath, uploaded_by) VALUES (%s, %s, %s)",
                            (filename, file_path, user_id))
                mysql.connection.commit()
                flash('File uploaded successfully!', 'success')
            except Exception as e:
                flash(f'Upload error: {e}', 'error')
            finally:
                cur.close()
        return redirect(url_for('home'))
    return render_template('upload.html')

@app.route('/download/<filename>')
def download_file(filename):
    if not filename:
        flash('Filename is missing.', 'error')
        return redirect(url_for('home'))
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found!', 'error')
        return redirect(url_for('home'))

@app.route('/backup', methods=['GET', 'POST'])
def backup():
    if request.method == 'POST':
        files_to_backup = request.form.getlist('files')
        # Backup the files
        for file_name in files_to_backup:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
            backup_path = os.path.join(app.config['BACKUP_FOLDER'], file_name)
            shutil.copy(file_path, backup_path)
    
        return redirect(url_for('home'))  # Use 'home' here
    
    files_in_uploads = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('backup.html', files_in_uploads=files_in_uploads)

@app.route('/delete/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    # Ensure user is logged in
    if 'username' not in session:  # Check for 'username' in session, based on your template
        flash('You need to log in first!', 'error')
        return redirect(url_for('login'))

    # Fetch the file info from the database
    cur = mysql.connection.cursor()
    cur.execute("SELECT filename FROM files WHERE id = %s", (file_id,))
    file = cur.fetchone()

    # Check if file exists
    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file[0])  # Path to the file on the server
        if os.path.exists(file_path):
            try:
                # Delete file from filesystem
                os.remove(file_path)
                # Remove file record from the database
                cur.execute("DELETE FROM files WHERE id = %s", (file_id,))
                mysql.connection.commit()
                flash('File deleted successfully', 'success')
            except Exception as e:
                flash(f'Error deleting file: {str(e)}', 'error')
        else:
            flash('File not found in the filesystem', 'error')
    else:
        flash('File not found in the database', 'error')

    cur.close()
    return redirect(url_for('home'))  # Make sure your 'home' route exists


# Restore route
@app.route('/restore', methods=['GET', 'POST'])
def restore():
	restored_files = []
	if request.method == 'POST':
		files_to_restore = request.form.getlist('files')
		cur = mysql.connection.cursor()
		try:
			for file_name in files_to_restore:
				try:
					shutil.copy(os.path.join(app.config['BACKUP_FOLDER'], file_name), os.path.join(app.config['UPLOAD_FOLDER'], file_name))
					file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
					# Add file info to database
					cur.execute("INSERT INTO files (filename,filepath, uploaded_by) VALUES (%s,%s, %s)",(file_name,file_path, session.get('user_id')))
					restored_files.append(file_name)

				except Exception as e:
					flash(f'Restore error: {e}', 'error')
			# Commit the transaction
			mysql.connection.commit()
			cur.close()
			if restored_files:
			    flash(f"Successfully restored files: {', '.join(restored_files)}", 'success')
		except Exception as e:
		    flash(f"Database error: {e}", 'error')

		flash('Files restored successfully!', 'success')
		return redirect(url_for('restore'))
	return render_template('restore.html', files_in_backup=os.listdir(app.config['BACKUP_FOLDER']))

# System monitoring route
@app.route('/system_monitoring')
def system_monitoring():
    uptime = timedelta(seconds=time.time() - psutil.boot_time())
    disk = psutil.disk_usage('/')
    return render_template('system_monitoring.html', uptime=str(uptime),
                           disk_total=f"{disk.total / (1024**3):.2f} GB",
                           disk_used=f"{disk.used / (1024**3):.2f} GB",
                           disk_free=f"{disk.free / (1024**3):.2f} GB",
                           disk_percent=disk.percent)

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
