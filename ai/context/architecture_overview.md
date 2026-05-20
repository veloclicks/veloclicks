# Architecture Overview

Veloclicks is a web application with a Python backend, a JavaScript/TypeScript frontend, external activity data ingestion from strava, database-backed storage, and an analysis pipeline that produces both deterministic metrics and LLM-ready summaries.

## Features
- Registration and Login
- Strava authentication
- Activity loading from strava
- View of activities and filtering
- Detailed activity view pages
- Activity analysis via a coach integrated with antrhopic api

## High-Level Components

### Backend
The backend is built in Python using Flask with an application factory pattern. It is responsible for:
- API endpoints
- orchestration of activity ingestion and analysis
- database access
- deterministic workout and ride analysis
- generation of compact structured summaries for LLM use
- integration with LLM providers

### Frontend
The frontend is built with Next.js and is responsible for:
- user-facing views including login, strava activity list, activity detail, user profile management
- presenting ride analysis and coaching insight
- interacting with backend APIs
- evolving independently from analysis internals where possible

### Data Store
- Locally postgres is the system of record for core application data and derived analysis artefacts
- Neon database is used in production

### Authentication
- User authentication against veloclicks is handled by JWT tokens
- User authentication against strava is handled by oauth

### External Integration
Strava is a key upstream data source and provides ride/activity data including streams such as power and heart rate when available.

### Deployment Platform
- Locally the platform runs as a Docker container
- IN Preoduction, zappa is used to deploy the entire app to an AWS lambda
- The end target is to get off zappa and move to a microservice-like architecture dominated by microservices as lightweight lambdas running flask

### flask app Directory Structure
- flask : parent
- .venv : IGNORE not code, this is python venv

- migrations : IGNORE this is for the database
- models : DATABASE : contains the data model for all domains
- output : Folder for writing output files to if needed aas part of the domain logic

- admin : IGNORE This is a command line interface, provides a cli entrypoint only, all logic should be delegated to the main domains
- ai_coach : IGNORE This is a beta feature, ignore for now
- analytics : IGNORE contains code for anlaysing an activity for a coach to assess - it does not have an api antrypoint
- auth : domain logic for user registration and login
- common : some common utilities
- profile : domain logic for managing a users profile including personal details and sports metrics such as heart rate xones, ftp, power zones
- strava : domain logic for anything to do with strava integration, retirevnig activities, retrieving activity streams etc
