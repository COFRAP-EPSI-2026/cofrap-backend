CREATE DATABASE IF NOT EXISTS cofrap
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE cofrap;

CREATE TABLE IF NOT EXISTS users (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password TEXT NULL,
    mfa      TEXT NULL,
    gendate  BIGINT NOT NULL,
    expired  TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_username (username),
    INDEX idx_expired_gendate (expired, gendate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
