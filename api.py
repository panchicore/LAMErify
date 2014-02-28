import os
import boto
import settings
import urllib
from werkzeug.utils import secure_filename
from flask import Flask, send_from_directory
from flask.ext import restful
from flask.ext.restful import reqparse
from subprocess import call
from datetime import datetime
from celery import Celery

def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

app = Flask(__name__)

api = restful.Api(app)

app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379',
    CELERY_RESULT_BACKEND='redis://localhost:6379'
)
celery = make_celery(app)

@celery.task(name="tasks.process_audio")
def process_audio(download_url, file_path_from, file_path_to, aws_upload, aws_access_key_id, aws_secret_access_key, aws_bucket, bucket_path):

    # download the original audio
    print '1. downloading...'
    local_filename, headers = urllib.urlretrieve(download_url, file_path_from)

    # lame it to MP3 and remove the original file after conversion
    print '2. encoding to mp3...'
    call(["lame", file_path_from, file_path_to, "-b 64"])
    os.remove(file_path_from)

    # upload to S3
    if aws_upload:
        filename = secure_filename(file_path_to)
        print filename
        s3 = boto.connect_s3(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        bucket = s3.create_bucket(aws_bucket)
        key = bucket.new_key(filename)

        key.key = bucket_path
        upload_file = open(file_path_to)

        AWS_HEADERS = {
            'x-amz-acl': 'public-read',
            'Cache-Control': 'max-age=86400',
        }

        print '3. uloading to aws...'
        key.set_contents_from_file(upload_file, headers=AWS_HEADERS,
                                   replace=True, cb=None, num_cb=10,
                                   policy=None, md5=None)

    print '- end'
    return True

@app.route("/")
def main():
    return "Welcome to Lamerify!"

class Encoder(restful.Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('key', type=str, location='form',
                                 required=True,
                                 help="key param needed, how are you going to relate the resource when I finish?")
        self.parser.add_argument('download_url', type=str, location='form',
                                 required=True,
                                 help="download_url param needed, where will I download the resource?")
        self.parser.add_argument('callback_url', type=str, location='form',
                                 required=True,
                                 help="callback_url param needed, where you will be notified about the enconding task?")
        self.parser.add_argument('aws_upload', type=int, required=False,
                                 default=0)
        self.parser.add_argument('aws_access_key_id', type=str, required=False,
                                 default=settings.AWS_ACCESS_KEY_ID)
        self.parser.add_argument('aws_secret_access_key', type=str,
                                 required=False, default=settings.AWS_SECRET_ACCESS_KEY)
        self.parser.add_argument('aws_bucket', type=str, required=False,
                                 default=settings.AWS_BUCKET_ID)

    def post(self):
        args = self.parser.parse_args()
        key = args['key']
        download_url = args['download_url']
        callback_url = args['callback_url']
        aws_upload = bool(args['aws_upload'])
        aws_access_key_id = args['aws_access_key_id']
        aws_secret_access_key = args['aws_secret_access_key']
        aws_bucket = args['aws_bucket']

        # resolve names and paths
        name = download_url.split('/')[-1].split('.')[0]
        extension = download_url.split('.')[-1]
        file_name_from = name + '.' + extension
        file_name_to = name + '.mp3'
        file_path_from = settings.STORAGE_FOLDER + file_name_from
        file_path_to = settings.STORAGE_FOLDER + file_name_to

        response = {'key': key,
                    'result_download_url': settings.STATIC_URL % file_name_to}

        t = datetime.today()
        bucket_path = '{0}/{1}/{2}/{3}'.format(t.year, t.month, t.day, file_name_to)
        response['aws_s3_url'] = 'https://s3.amazonaws.com/{0}/{1}'.format(
            aws_bucket, bucket_path
        )

        process_audio.delay(download_url, file_path_from, file_path_to, aws_upload, aws_access_key_id, aws_secret_access_key, aws_bucket, bucket_path)

        return response, 200


class Download(restful.Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('filename', type=str, required=True,
                                 help="And the filename?")

    def get(self, filename):
        file = send_from_directory(settings.STORAGE_FOLDER, filename)
        return file

api.add_resource(Encoder, '/encoder')
api.add_resource(Download, '/download/<filename>')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=settings.PORT, debug=settings.DEBUG)
