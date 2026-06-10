from flask import Flask, request, jsonify, send_file, abort, session, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime
import os, base64, io

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'admin-secret-key-121')

# ── Database ─────────────────────────────────────────────────────
db_url = os.environ.get('DATABASE_URL')
if not db_url or 'yourpassword' in db_url or 'postgres:password' in db_url:
    # Local fallback: points to sqlite database of mirror-user
    db_url = 'sqlite:///' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mirror-user', 'mirror.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

# ── Database model (Same Shared Table) ────────────────────────────
class CapturedImage(db.Model):
    __tablename__ = 'captured_images'
    id          = db.Column(db.Integer, primary_key=True)
    image_data  = db.Column(db.Text, nullable=False)  # Base64 string
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)
    compliment  = db.Column(db.String(200), nullable=True)

# ── Admin Auth ───────────────────────────────────────────────────
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '@Ankush121')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ════════════════════════════════════════════════════════════════
#  ADMIN PANEL ROUTES
# ════════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))
        error = 'Incorrect password.'
    return render_template('index.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@admin_required
def dashboard():
    page   = request.args.get('page', 1, type=int)
    images = CapturedImage.query.order_by(
        CapturedImage.captured_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    total  = CapturedImage.query.count()
    return render_template('about.html', images=images, total=total)

@app.route('/image/<int:img_id>')
@admin_required
def serve_image(img_id):
    """Serve image decoded directly from database."""
    img = CapturedImage.query.get_or_404(img_id)
    img_bytes = base64.b64decode(img.image_data)
    return send_file(io.BytesIO(img_bytes), mimetype='image/jpeg')
@app.route('/download/<int:img_id>')
@admin_required
def download_image(img_id):
    """Download image decoded directly from database."""
    img = CapturedImage.query.get_or_404(img_id)
    img_bytes = base64.b64decode(img.image_data)
    return send_file(
        io.BytesIO(img_bytes),
        download_name=f"pose_{img.id}.jpg",
        as_attachment=True,
        mimetype='image/jpeg'
    )

@app.route('/download-all')
@admin_required
def download_all():
    """ZIP and download all captured images from database."""
    import zipfile
    images = CapturedImage.query.all()
    if not images:
        return 'No images captured yet.', 200
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for img in images:
            img_bytes = base64.b64decode(img.image_data)
            filename = f"pose_{img.id}_{img.captured_at.strftime('%Y%m%d%H%M%S')}.jpg"
            zf.writestr(filename, img_bytes)
    buf.seek(0)
    return send_file(
        buf,
        download_name='mirror_captures.zip',
        as_attachment=True,
        mimetype='application/zip'
    )

@app.route('/delete/<int:img_id>')
@admin_required
def delete_image(img_id):
    """Delete image from DB."""
    img = CapturedImage.query.get_or_404(img_id)
    db.session.delete(img)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete-all')
@admin_required
def delete_all():
    """Delete all captured images from DB."""
    try:
        db.session.query(CapturedImage).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()
    return redirect(url_for('dashboard'))

@app.route('/api/count')
@admin_required
def api_count():
    """Returns the total number of captured images in database."""
    total = CapturedImage.query.count()
    return jsonify({'total': total})

if __name__ == '__main__':
    # Running Admin Panel on port 5001
    app.run(debug=True, host='0.0.0.0', port=5001)
