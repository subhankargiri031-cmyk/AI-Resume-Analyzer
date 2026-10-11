
CREATE DATABASE IF NOT EXISTS resume_matcher;

USE resume_matcher;

CREATE TABLE IF NOT EXISTS analysis_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_name VARCHAR(100) NOT NULL,
    resume_filename VARCHAR(255) NOT NULL,
    resume_skills TEXT NOT NULL,
    job_description LONGTEXT NOT NULL,
    required_skills TEXT NOT NULL,
    matched_skills TEXT NOT NULL,
    missing_skills TEXT NOT NULL,
    match_score DECIMAL(5,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
