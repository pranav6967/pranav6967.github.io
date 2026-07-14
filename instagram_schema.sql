-- ============================================
-- Instagram-like Database Schema (PostgreSQL)
-- ============================================

-- USERS
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(30) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    bio VARCHAR(150),
    profile_pic_url TEXT,
    is_private BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- POSTS
CREATE TABLE posts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    caption TEXT,
    location VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- POST MEDIA (supports carousel posts: multiple images/videos per post)
CREATE TABLE post_media (
    id BIGSERIAL PRIMARY KEY,
    post_id BIGINT REFERENCES posts(id) ON DELETE CASCADE,
    media_url TEXT NOT NULL,
    media_type VARCHAR(10) CHECK (media_type IN ('image','video')),
    position INT DEFAULT 0
);

-- FOLLOWS
CREATE TABLE follows (
    follower_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    following_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(10) DEFAULT 'accepted' CHECK (status IN ('pending','accepted')),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (follower_id, following_id)
);

-- LIKES
CREATE TABLE likes (
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    post_id BIGINT REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

-- COMMENTS
CREATE TABLE comments (
    id BIGSERIAL PRIMARY KEY,
    post_id BIGINT REFERENCES posts(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    parent_comment_id BIGINT REFERENCES comments(id),
    content VARCHAR(2200) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- COMMENT LIKES
CREATE TABLE comment_likes (
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    comment_id BIGINT REFERENCES comments(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, comment_id)
);

-- STORIES (24hr expiry)
CREATE TABLE stories (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    media_url TEXT NOT NULL,
    media_type VARCHAR(10) CHECK (media_type IN ('image','video')),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '24 hours'
);

-- STORY VIEWS
CREATE TABLE story_views (
    story_id BIGINT REFERENCES stories(id) ON DELETE CASCADE,
    viewer_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    viewed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (story_id, viewer_id)
);

-- DIRECT MESSAGES
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    sender_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    receiver_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    content TEXT,
    media_url TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- HASHTAGS
CREATE TABLE hashtags (
    id BIGSERIAL PRIMARY KEY,
    tag VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE post_hashtags (
    post_id BIGINT REFERENCES posts(id) ON DELETE CASCADE,
    hashtag_id BIGINT REFERENCES hashtags(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, hashtag_id)
);

-- ============================================
-- Helpful indexes
-- ============================================
CREATE INDEX idx_posts_user ON posts(user_id);
CREATE INDEX idx_comments_post ON comments(post_id);
CREATE INDEX idx_follows_following ON follows(following_id);
CREATE INDEX idx_stories_expires ON stories(expires_at);
CREATE INDEX idx_messages_sender_receiver ON messages(sender_id, receiver_id);
CREATE INDEX idx_post_media_post ON post_media(post_id);
