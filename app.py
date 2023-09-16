import os
from datetime import datetime
from flask import Flask, render_template, request, send_from_directory, redirect, url_for

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'

# Ensure the uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def index():
    # Get all the images from the uploads directory
    all_images = [img for img in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], img))]
    if request.method == 'POST':
        image = request.files['imageInput']
        filename_parts = os.path.splitext(image.filename)
        unique_filename = f"{filename_parts[0]}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{filename_parts[1]}"
        unique_filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)   
        image.save(unique_filepath)
        return redirect(url_for('index'))  
    return render_template('index.html', images=all_images)