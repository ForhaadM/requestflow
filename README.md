# RequestFlow
[![CI](https://github.com/ForhaadM/requestflow/actions/workflows/ci.yml/badge.svg)](https://github.com/ForhaadM/requestflow/actions/workflows/ci.yml)

A full-stack internal request management system for tracking approvals, reviews, and SLAs.

## Overview / Problem Statement

Internal teams routinely need a way to submit requests (access, hardware, software, bug reports), route them to the right reviewer, and track their status from submission to resolution. RequestFlow models this end-to-end workflow with role-based permissions (requester, reviewer, admin), a conditional business rule requiring justification on rejected requests, and a full audit trail of who reviewed what and when.

This project was built to demonstrate both software engineering skills (schema design, REST API development, authentication, containerization, cloud deployment) and business analysis skills (requirements modeling, workflow design, deliberate scoping decisions) relevant to both SWE and BA roles.

## Features

- **Request submission** — requesters submit categorized requests (access, hardware, software, bug report) with a priority level
- **Review workflow** — reviewers approve or reject requests; rejections require a written justification, enforced at the application layer
- **Role-based access** — requester, reviewer, and admin roles with distinct permissions
- **Authentication** — JWT-based auth with bcrypt password hashing; identity for all actions is derived from a verified token, never from client-supplied input
- **Admin dashboard** — full visibility into all requests and reviews across the system
- **Audit trail** — every review is its own timestamped record tied to the reviewer and the request

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0
- **Database:** PostgreSQL
- **Frontend:** React, Vite, Tailwind CSS
- **Auth:** JWT (python-jose), bcrypt (passlib)
- **Testing:** pytest, FastAPI TestClient
- **Infra:** Docker, Docker Compose, GitHub Actions (CI/CD)
- **Cloud:** AWS (RDS, EC2, S3, CloudFront, Route 53)

## Data Model / Architecture

Three core entities: `users`, `requests`, and `reviews`.
