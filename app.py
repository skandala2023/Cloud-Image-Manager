import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, g
import jwt

from google.oauth2 import id_token
from google.auth.transport import requests

from google.cloud import storage, datastore

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './service-account-key.json'

app = Flask(__name__)
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
CLIENT_ID = os.environ.get("CLIENT_ID")

storage_client = storage.Client()
datastore_client = datastore.Client()

BUCKET_NAME = os.environ.get("BUCKET_NAME")


@app.before_request
def request_logger():
    print("--------------------------------------")
    print(request.method, "-", request.path)


def is_user_logged_in():
    jwt_cookie = request.cookies.get('jwt')
    print("jwt -", jwt_cookie)

    if jwt_cookie:
        try:
            decoded_token = jwt.decode(jwt_cookie, JWT_SECRET_KEY, algorithms=[
                                       'HS256'])

            user_email = decoded_token.get('email')

            if user_email:
                g.email = user_email
                return True
        except jwt.ExpiredSignatureError:
            return False
        except jwt.DecodeError:
            return False

    return False


@app.before_request
def protect():
    logged_in = is_user_logged_in()
    if logged_in:
        print("USER LOGGED IN!")
        if request.endpoint == "login":
            return redirect("/")
    elif request.endpoint != "login":
        print("USER NOT LOGGED IN!")
        return redirect(url_for('login'))
    else:
        print("USER NOT LOGGED IN!")


def verify_credential(idToken):
    userInfo = id_token.verify_oauth2_token(
        idToken, requests.Request(), CLIENT_ID, clock_skew_in_seconds=10)

    return userInfo


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        idToken = request.json.get("idToken")

        user = verify_credential(idToken)
        if user:
            token = jwt.encode({'email': user["email"], "name": user["name"]},
                               JWT_SECRET_KEY, algorithm='HS256')

            response = make_response(redirect(url_for("index"), code=303))
            response.set_cookie("jwt", token, httponly=True)

            return response
        else:
            flash('Invalid username or password', 'error')
    else:
        return render_template('login.html', client_id=CLIENT_ID)


@app.route("/logout", methods=["POST"])
def logout():
    response = make_response(redirect(url_for("login")))
    response.set_cookie('jwt', '', expires=0)
    return response


@app.route('/', methods=['GET', 'POST'])
def index():
    email = g.get('email', '')

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
            'user': email,
            'uploaded_at': datetime.utcnow()
        })
        datastore_client.put(entity)

        return redirect(url_for('index'))

    # Fetch all image metadata from Datastore
    query = datastore_client.query(kind='Image')
    query = query.add_filter(
        filter=datastore.query.PropertyFilter('user', '=', email))
    all_images = list(query.fetch())
    all_images = [image['filename'] for image in all_images]
    print(all_images)

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
    app.secret_key = 'super secret key'
    app.config['SESSION_TYPE'] = 'filesystem'

    app.run(host='0.0.0.0', debug=True)
