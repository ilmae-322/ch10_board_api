async def add_comment(client, headers, post_id, content="댓글"):
    response = await client.post(f"/posts/{post_id}/comments", headers=headers, json={"content": content})
    assert response.status_code == 201, response.text
    return response.json()


# ---------- 댓글 ----------


async def test_create_and_list_comments_in_written_order(client, alice, bob, post):
    await add_comment(client, bob, post["id"], "첫 댓글")
    await add_comment(client, alice, post["id"], "두 번째 댓글")

    response = await client.get(f"/posts/{post['id']}/comments")

    assert response.status_code == 200
    body = response.json()
    assert [item["content"] for item in body["items"]] == ["첫 댓글", "두 번째 댓글"]
    assert body["items"][0]["author"]["nickname"] == "바비"
    assert body["total"] == 2


async def test_comment_count_appears_on_post_and_list(client, bob, post):
    await client.get("/posts")  # 목록을 캐시에 올려 둔다.
    await add_comment(client, bob, post["id"])

    single = await client.get(f"/posts/{post['id']}")
    listed = await client.get("/posts")

    assert single.json()["comment_count"] == 1
    assert listed.headers["x-cache"] == "MISS"  # 댓글 작성으로 캐시가 무효화됨
    assert listed.json()["items"][0]["comment_count"] == 1


async def test_comment_requires_login(client, post):
    response = await client.post(f"/posts/{post['id']}/comments", json={"content": "익명"})

    assert response.status_code == 401


async def test_comment_on_missing_post_is_404(client, alice):
    create = await client.post("/posts/999/comments", headers=alice, json={"content": "댓글"})
    listing = await client.get("/posts/999/comments")

    assert create.status_code == listing.status_code == 404


async def test_blank_comment_is_422(client, alice, post):
    response = await client.post(f"/posts/{post['id']}/comments", headers=alice, json={"content": "  "})

    assert response.status_code == 422


async def test_update_comment_by_author_only(client, alice, bob, post):
    comment = await add_comment(client, bob, post["id"], "원래 댓글")

    by_other = await client.patch(f"/comments/{comment['id']}", headers=alice, json={"content": "x"})
    by_author = await client.patch(f"/comments/{comment['id']}", headers=bob, json={"content": "고침"})

    assert by_other.status_code == 403
    assert by_author.status_code == 200
    assert by_author.json()["content"] == "고침"


async def test_delete_comment_by_author_or_admin(client, alice, bob, admin, post):
    first = await add_comment(client, bob, post["id"])
    second = await add_comment(client, bob, post["id"])

    by_other = await client.delete(f"/comments/{first['id']}", headers=alice)
    by_author = await client.delete(f"/comments/{first['id']}", headers=bob)
    by_admin = await client.delete(f"/comments/{second['id']}", headers=admin)

    assert by_other.status_code == 403
    assert by_author.status_code == by_admin.status_code == 204
    assert (await client.get(f"/posts/{post['id']}")).json()["comment_count"] == 0


async def test_missing_comment_is_404(client, alice):
    response = await client.patch("/comments/999", headers=alice, json={"content": "x"})

    assert response.status_code == 404
    assert response.json()["code"] == "COMMENT_NOT_FOUND"


# ---------- 좋아요 ----------


async def test_like_is_idempotent_per_user(client, alice, bob, post):
    first = await client.put(f"/posts/{post['id']}/like", headers=bob)
    again = await client.put(f"/posts/{post['id']}/like", headers=bob)
    other = await client.put(f"/posts/{post['id']}/like", headers=alice)

    assert first.status_code == 200
    assert first.json() == {"post_id": post["id"], "liked": True, "like_count": 1}
    assert again.json()["like_count"] == 1
    assert other.json()["like_count"] == 2
    assert (await client.get(f"/posts/{post['id']}")).json()["like_count"] == 2


async def test_unlike_is_idempotent(client, bob, post):
    await client.put(f"/posts/{post['id']}/like", headers=bob)

    first = await client.delete(f"/posts/{post['id']}/like", headers=bob)
    again = await client.delete(f"/posts/{post['id']}/like", headers=bob)

    assert first.json() == {"post_id": post["id"], "liked": False, "like_count": 0}
    assert again.status_code == 200 and again.json()["like_count"] == 0


async def test_like_requires_login_and_existing_post(client, alice, post):
    anonymous = await client.put(f"/posts/{post['id']}/like")
    missing = await client.put("/posts/999/like", headers=alice)

    assert anonymous.status_code == 401
    assert missing.status_code == 404
