import cloudinary
import cloudinary.uploader


def init_cloudinary(app):
    cloudinary.config(
        cloud_name=app.config['CLOUDINARY_CLOUD_NAME'],
        api_key=app.config['CLOUDINARY_API_KEY'],
        api_secret=app.config['CLOUDINARY_API_SECRET'],
        secure=True,
    )


def upload_photo(file_stream, folder='memorials', transformation=None):
    """Upload a file to Cloudinary. Returns (url, public_id) or raises."""
    options = {'folder': folder, 'resource_type': 'image'}
    if transformation:
        options['transformation'] = transformation
    result = cloudinary.uploader.upload(file_stream, **options)
    return result['secure_url'], result['public_id']


def delete_photo(public_id):
    """Delete a photo from Cloudinary by public_id."""
    if public_id:
        cloudinary.uploader.destroy(public_id)
