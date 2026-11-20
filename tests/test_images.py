from pathlib import Path

from app.core.config import get_settings

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


def stored_files() -> set[str]:
    return {path.name for path in Path(get_settings().upload_dir).iterdir()}


async def upload(client, headers, post_id, content, filename="image.png", content_type="image/png"):
    return await client.post(
        f"/posts/{post_id}/image",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )


async def test_upload_image_and_download_it(client, alice, post):
    response = await upload(client, alice, post["id"], PNG)

    assert response.status_code == 200
    image_url = response.json()["image_url"]
    assert image_url.startswith("/uploads/") and image_url.endswith(".png")

    downloaded = await client.get(image_url)
    assert downloaded.status_code == 200
    assert downloaded.content == PNG


async def test_extension_comes_from_file_content_not_client(client, alice, post):
    # 클라이언트가 PNG라고 주장해도 실제 내용이 JPEG면 .jpg로 저장한다.
    response = await upload(client, alice, post["id"], JPEG, filename="evil.php")

    assert response.status_code == 200
    assert response.json()["image_url"].endswith(".jpg")


async def test_webp_is_accepted(client, alice, post):
    response = await upload(client, alice, post["id"], WEBP, content_type="image/webp")

    assert response.status_code == 200
    assert response.json()["image_url"].endswith(".webp")


async def test_html_disguised_as_png_is_rejected(client, alice, post):
    before = stored_files()

    response = await upload(client, alice, post["id"], b"<html><script>alert(1)</script></html>")

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_FILE"
    assert stored_files() == before


async def test_empty_file_is_rejected(client, alice, post):
    response = await upload(client, alice, post["id"], b"")

    assert response.status_code == 400


async def test_too_large_file_is_rejected_and_not_left_on_disk(client, alice, post, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 100)
    before = stored_files()

    response = await upload(client, alice, post["id"], PNG + b"\x00" * 200)

    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"
    assert stored_files() == before


async def test_only_author_can_upload(client, bob, post):
    response = await upload(client, bob, post["id"], PNG)

    assert response.status_code == 403


async def test_replacing_image_deletes_old_file(client, alice, post):
    first = (await upload(client, alice, post["id"], PNG)).json()["image_url"]
    second = (await upload(client, alice, post["id"], JPEG)).json()["image_url"]

    files = stored_files()
    assert Path(second).name in files
    assert Path(first).name not in files


async def test_deleting_post_deletes_image_file(client, alice, post):
    image_url = (await upload(client, alice, post["id"], PNG)).json()["image_url"]

    await client.delete(f"/posts/{post['id']}", headers=alice)

    assert Path(image_url).name not in stored_files()
