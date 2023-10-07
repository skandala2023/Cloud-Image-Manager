import os
from datetime import datetime
from flask import Flask, render_template, request, send_from_directory, redirect, url_for

from google.cloud import storage, datastore

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './service-account-key.json'

app = Flask(__name__)

storage_client = storage.Client()
datastore_client = datastore.Client()

BUCKET_NAME = 'image-uploads-2023'


@app.route('/', methods=['GET', 'POST'])
def index():
    # Fetch all image metadata from Datastore
    query = datastore_client.query(kind='Image')
    all_images = list(query.fetch())
    all_images = [image['filename'] for image in all_images]
    print(all_images)

    if request.method == 'POST':
        image = request.files['imageInput']
        filename_parts = os.path.splitext(image.filename)
        unique_filename = f"{filename_parts[0]}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}{filename_parts[1]}"

        # Upload image to GCP Storage
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(unique_filename)
        blob.upload_from_string(
            image.read(),
            content_type=image.content_type
        )

        # Save image metadata to Datastore
        entity = datastore.Entity(
            key=datastore_client.key('Image', unique_filename))
        entity.update({
            'filename': unique_filename,
            'uploaded_at': datetime.utcnow()
        })
        datastore_client.put(entity)

        return redirect(url_for('index'))

    return render_template('index.html', images=all_images)


@app.route('/view/<filename>')
def view_image(filename):
    image_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
    return render_template('view.html', image_url=image_url, filename=filename)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    image_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
    return redirect(image_url)


@app.route('/delete/<filename>')
def delete_image(filename):
    # Delete image from GCP Storage
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.delete()

    # Delete image metadata from Datastore
    key = datastore_client.key('Image', filename)
    datastore_client.delete(key)

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
