from app.routers.common import MAX_DB_ID, MAX_PAGE


async def create(client, headers, title="제목", content="내용"):
    response = await client.post("/posts", headers=headers, json={"title": title, "content": content})
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_post_sets_author_from_token(client, alice):
    response = await client.post(
        "/posts", headers=alice, json={"title": "  제목  ", "content": "내용"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "제목"
    assert body["author"] == {"id": 1, "nickname": "앨리스"}
    assert body["like_count"] == 0 and body["comment_count"] == 0
    assert body["image_url"] is None


async def test_create_post_requires_login(client):
    response = await client.post("/posts", json={"title": "제목", "content": "내용"})

    assert response.status_code == 401


async def test_create_post_rejects_blank_title(client, alice):
    response = await client.post("/posts", headers=alice, json={"title": "   ", "content": "내용"})

    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "title"


async def test_list_posts_paginates_newest_first(client, alice):
    for number in range(1, 6):
        await create(client, alice, title=f"글 {number}")

    response = await client.get("/posts", params={"page": 2, "size": 2})

    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["items"]] == ["글 3", "글 2"]
    assert body["total"] == 5 and body["total_pages"] == 3


async def test_list_posts_keyword_searches_title_and_content(client, alice):
    await create(client, alice, title="FastAPI 입문", content="...")
    await create(client, alice, title="다른 글", content="fastapi 내용")
    await create(client, alice, title="관계없음", content="...")

    response = await client.get("/posts", params={"keyword": "FASTAPI"})

    assert response.json()["total"] == 2


async def test_list_posts_keyword_treats_wildcards_literally(client, alice):
    await create(client, alice, title="할인 100%", content="...")
    await create(client, alice, title="snake_case", content="...")
    await create(client, alice, title="평범한 글", content="...")

    percent = await client.get("/posts", params={"keyword": "%"})
    underscore = await client.get("/posts", params={"keyword": "_"})

    assert [item["title"] for item in percent.json()["items"]] == ["할인 100%"]
    assert [item["title"] for item in underscore.json()["items"]] == ["snake_case"]


async def test_list_posts_cache_hit_and_invalidation(client, alice):
    first = await client.get("/posts")
    second = await client.get("/posts")
    assert (first.headers["x-cache"], second.headers["x-cache"]) == ("MISS", "HIT")

    await create(client, alice)
    after_write = await client.get("/posts")

    assert after_write.headers["x-cache"] == "MISS"
    assert after_write.json()["total"] == 1


async def test_read_post_not_found(client):
    response = await client.get("/posts/999")

    assert response.status_code == 404
    assert response.json()["code"] == "POST_NOT_FOUND"


async def test_out_of_range_numbers_are_422_not_500(client):
    too_big_id = await client.get(f"/posts/{MAX_DB_ID + 1}")
    too_big_page = await client.get("/posts", params={"page": MAX_PAGE + 1})
    huge_page = await client.get("/posts", params={"page": 10**18})

    assert too_big_id.status_code == 422
    assert too_big_page.status_code == 422
    assert huge_page.status_code == 422


async def test_update_post_by_author_changes_only_sent_fields(client, alice, post):
    response = await client.patch(f"/posts/{post['id']}", headers=alice, json={"title": "수정"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "수정"
    assert body["content"] == post["content"]
    assert body["updated_at"] >= post["updated_at"]


async def test_update_post_requires_at_least_one_field(client, alice, post):
    response = await client.patch(f"/posts/{post['id']}", headers=alice, json={})

    assert response.status_code == 422


async def test_update_post_by_other_user_is_403(client, bob, post):
    response = await client.patch(f"/posts/{post['id']}", headers=bob, json={"title": "탈취"})

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_delete_post_by_other_user_is_403(client, bob, post):
    response = await client.delete(f"/posts/{post['id']}", headers=bob)

    assert response.status_code == 403


async def test_delete_post_by_author(client, alice, post):
    response = await client.delete(f"/posts/{post['id']}", headers=alice)

    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(f"/posts/{post['id']}")).status_code == 404


async def test_admin_can_delete_but_not_edit_others_post(client, admin, post):
    edit = await client.patch(f"/posts/{post['id']}", headers=admin, json={"title": "관리자"})
    remove = await client.delete(f"/posts/{post['id']}", headers=admin)

    assert edit.status_code == 403
    assert remove.status_code == 204


async def test_deleting_post_removes_its_comments_and_likes(client, alice, bob, post):
    comment = await client.post(
        f"/posts/{post['id']}/comments", headers=bob, json={"content": "댓글"}
    )
    await client.put(f"/posts/{post['id']}/like", headers=bob)

    await client.delete(f"/posts/{post['id']}", headers=alice)

    deleted_comment = await client.delete(f"/comments/{comment.json()['id']}", headers=bob)
    assert deleted_comment.status_code == 404
