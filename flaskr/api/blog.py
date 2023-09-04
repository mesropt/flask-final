import functools
from typing import Optional
from dataclasses import asdict
import jwt
from flask import Blueprint, request, make_response, jsonify, current_app

from flaskr.models import Post, BlackJWToken
from flaskr.validations import validate_post_form


blog_blueprint = Blueprint("blogAPI", __name__, url_prefix="/api/blog")


def _decode_auth_token(auth_token: str) -> tuple[Optional[int], Optional[str]]:
    try:
        payload = jwt.decode(
            auth_token, current_app.config.get("SECRET_KEY"), algorithms=["HS256"]
        )
        return int(payload["sub"]), None
    except jwt.ExpiredSignatureError:
        return None, "Signature expired"
    except jwt.InvalidTokenError:
        return None, "Invalid token"


@blog_blueprint.route("/", methods=["GET"])
def index():
    resp = []
    for post in Post.get_all():
        resp.append(asdict(post))
    return make_response(jsonify(resp)), 200


def auth_required(handler):
    @functools.wraps(handler)
    def wrapped_view(**kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            responseObject = {
                "status": "fail",
                "message": "Missing Authorization Header",
            }
            return make_response(jsonify(responseObject)), 400

        _, token = auth_header.split(" ")

        if BlackJWToken(token).is_blacklisted():
            responseObject = {
                "status": "fail",
                "message": "Token Blacklisted",
            }
            return make_response(jsonify(responseObject)), 400
        
        user_id, err = _decode_auth_token(token)
        if err:
            responseObject = {"status": "fail", "message": err}
            return make_response(jsonify(responseObject)), 400

        return handler(**kwargs, user_id=user_id)

    return wrapped_view


@blog_blueprint.route("/create", methods=["POST"])
@auth_required
def create(user_id: int):
    post_data = request.get_json()
    if err := validate_post_form(post_data):
        response = {"status": "fail", "message": err}
        return make_response(jsonify(response)), 400

    post = Post(author_id=user_id, title=post_data["title"], body=post_data["body"])
    post.commit()

    return (
        make_response(
            jsonify(
                {
                    "status": "success",
                    "message": "New Post Created",
                    "post": asdict(post),
                }
            )
        ),
        201,
    )


@blog_blueprint.route("/update/<int:id>", methods=["POST"])
@auth_required
def update(id: int, user_id: int):
    post_data = request.get_json()
    if err := validate_post_form(post_data):
        response = {"status": "fail", "message": err}
        return make_response(jsonify(response)), 400

    post = Post.get_by_id(id)
    if post is None:
        response = {"status": "fail", "message": f"Failed to Find Post: {id}"}
        return make_response(jsonify(response)), 404

    if post.author_id != user_id:
        response = {"status": "fail", "message": "Permission Denied"}
        return make_response(jsonify(response)), 403

    post.update(post_data["title"], post_data["body"])

    return (
        make_response(
            jsonify(
                {"status": "success", "message": "Post Updated", "post": asdict(post)}
            )
        ),
        201,
    )
