# Real Estate Listing & Market Analysis System

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![Vanilla JS](https://img.shields.io/badge/Vanilla_JS-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)

A high-performance market analysis and listing management system designed to process, store, and analyze real estate data at scale. This project features a robust **FastAPI** backend, a fully indexed and optimized **PostgreSQL** database, and a highly responsive dashboard built using **Vanilla CSS and Javascript** with **Chart.js** for visual data insights.

---

## &#x1F680; Key Features

&bull; **Scalable Data Ingestion (ETL)**: Robust Python ETL pipelines that parse, clean (handles NaN values, data type normalization), and seed **180,000+ real estate records** representing various regions and listing types in India.
&bull; **Sub-Second Analytics Engine**: Custom SQL queries with PostgreSQL materialized views and composite indexes, delivering sub-second response times on aggregate queries across large datasets.
&bull; **Interactive Market Dashboard**:
  &bull; Real-time metrics on average prices, price per sq ft, and total listings.
    &bull; Interactive geographical and temporal breakdown charts using Chart.js.
      &bull; Dynamic filters for price range, city, listing types, and dates.
      &bull; **Full CRUD Functionality**: Modern APIs to create, read, update, and delete listings with data validation powered by Pydantic.
      &bull; **Dockerized Setup**: Multi-container architecture orchestrating the backend, database, and client services seamlessly.

      ---

      ## &#x1F4D0; System Architecture

      ```mermaid
      graph TD
          Client[Web Dashboard: HTML5/CSS3/Vanilla JS] <--> |JSON API / REST| Backend[FastAPI Server]
              Backend <--> |SQLAlchemy ORM / Raw SQL| DB[(PostgreSQL Database)]
                  DB --> |Indexes & Materialized Views| DB
                      ETL[Python Seeder Script] --> |Bulk Insert / Cleaned Data| DB
                      ```

                      ---

                      ## &#x1F6E0; Tech Stack

                      &bull; **Backend**: FastAPI, Python 3.10+, SQLAlchemy (ORM), Pydantic
                      &bull; **Database**: PostgreSQL (relational storage, custom indexing, aggregations)
                      &bull; **Frontend**: HTML5, Vanilla CSS3 (custom CSS design variables, sleek glassmorphism dashboard UI), Vanilla JavaScript, Chart.js
                      &bull; **DevOps**: Docker, Docker Compose, Git

                      ---

                      ## &#x1F4BB; Installation & Setup

                      ### Prerequisites
                      &bull; Docker & Docker Compose installed on your system.
                      &bull; Alternatively: Python 3.10+ and PostgreSQL installed locally.

                      ### Running with Docker (Recommended)
                      1\. **Clone the repository**:
                         ```bash
                            git clone https://github.com/gargdev07/real_estate_project.git
                               cd real_estate_project
                                  ```

                                  2\. **Launch the environment**:
                                     ```bash
                                        docker-compose up -d --build
                                           ```
                                              *This starts the PostgreSQL database and the FastAPI application.*

                                              3\. **Ingest the dataset**:
                                                 Once the containers are up, seed the database with listing records:
                                                    ```bash
                                                       docker-compose exec web python scripts/seed_db.py
                                                          ```

                                                          4\. **Access the Application**:
                                                             &bull; Dashboard Frontend: Open `http://localhost:8000` (or the configured client port) in your browser.
                                                                &bull; API Documentation (Swagger UI): Navigate to `http://localhost:8000/docs`.

                                                                ---

                                                                ## &#x1F4C2; Project Structure

                                                                ```
                                                                |-- app/                  # FastAPI Application Source Code
                                                                |   |-- main.py           # Application Entrypoint & Middleware
                                                                |   |-- models.py         # SQLAlchemy Database Schemas
                                                                |   |-- schemas.py        # Pydantic Schemas for Request/Response Validation
                                                                |   |-- crud.py           # Database Query Logic & CRUD Actions
                                                                |   `-- database.py       # DB Session & Connection Setup
                                                                |-- static/               # Client Assets
                                                                |   |-- css/              # Vanilla CSS stylesheets (custom design variables)
                                                                |   `-- js/               # Frontend Logic & Chart.js rendering
                                                                |-- scripts/              # Database maintenance and ingestion scripts
                                                                |   `-- seed_db.py        # Clean, parse, and insert listing datasets
                                                                |-- docker-compose.yml    # Multi-container configuration
                                                                |-- Dockerfile            # Container definition for web app
                                                                `-- requirements.txt      # Python dependencies
                                                                ```

                                                                ---

                                                                ## &#x1F4C8; Performance Engineering Highlights

                                                                &bull; **Bulk Inserts**: The seeder utilizes SQL bulk copy and transaction grouping to seed 180,000+ rows in less than 30 seconds.
                                                                &bull; **Indexing Strategy**: Implemented B-Tree indexes on frequently queried columns (`city`, `price`, `type`) and GIST/GIN indexes for textual searches, lowering search times from ~450ms to <15ms.
                                                                &bull; **Materialized Views**: Periodic aggregations are stored in materialized views to bypass intensive table joins on real-time dashboard loads.
                                                                
