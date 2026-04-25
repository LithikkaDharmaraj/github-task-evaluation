# AI Github Task Evaluation System  

### 🔷 Overview

The **AI-Powered Task Evaluation System** is a production-grade platform designed to **automatically evaluate developer assignments** using AI.

Instead of manually reviewing candidate submissions, this system analyzes a GitHub repository against a given **project title and description**, and generates a **structured, objective hiring report**.

It combines:
- File-level code analysis  
- LLM-based reasoning (LLaMA 3.3 via Groq)  
- Static analysis & metrics  
- Multi-parameter scoring  

to determine whether a candidate has **actually built what was asked**.

---

### 🧩 System Approach

This system automates evaluation by:

- Cloning the candidate’s GitHub repository  
- Understanding the **task requirements**  
- Analyzing all relevant files  
- Matching implementation with expectations  
- Scoring across multiple dimensions  
- Generating a **complete hiring recommendation**

---

### ⚡ Key Features

**Requirement-Aware Evaluation**

- Evaluates projects **based on the given task**
- Detects **missing or partially implemented features**

**File-Level Intelligence**

- Understands each file’s role
- Maps files to features
- Identifies gaps and redundancies

**LLM-Powered Reasoning (LLaMA 3.3 via Groq)**

- Context-aware evaluation of codebase
- Human-like feedback generation
- Interview-style insights and suggestions

**Advanced Scoring System**

Projects are evaluated across:

- Relevance to task  
- Accuracy of implementation  
- Feature completeness  
- Code quality & maintainability  
- Architecture & modularity  
- Performance (latency & efficiency)  
- Security & validation  
- Error handling  
- Database design (PostgreSQL)  
- Documentation & deployment readiness  

**Real-Time Progress Tracking**

- Live evaluation updates using streaming

**Persistent Evaluation Storage**

- All evaluations stored using PostgreSQL
- Supports history and re-evaluation

---

### 📌 Evaluation Parameters

| Parameter | Description |
|----------|------------|
| Relevance | Matches project with given task |
| Accuracy | Correctness of implementation |
| Completeness | Coverage of required features |
| Code Quality | Clean, readable, maintainable code |
| Architecture | Proper project structure |
| Performance | Efficient and low-latency execution |
| Security | Safe coding practices |
| Error Handling | Robust failure handling |
| Database Design | Proper PostgreSQL usage |
| Documentation | Clarity and completeness |

---

### 🔻 Tech Stack

| Layer              | Technology |
|--------------------|------------|
| Frontend           | React, Vite |
| Backend            | FastAPI (Python) |
| Database           | PostgreSQL (SQLAlchemy ORM) |
| LLM                | LLaMA 3.3 via Groq API |
| Code Parsing       | tree-sitter |
| Static Analysis    | Semgrep, Bandit |
| Metrics            | Radon, Lizard |
| Repo Handling      | GitPython |
| Streaming          | Server-Sent Events (SSE) |

---

### 🔄 System Workflow

User Input

├── GitHub Repo URL

├── Project Title

└── Project Description

↓
Repository Cloning

↓
File Filtering (ignore node_modules, build, etc.)

↓
Code Parsing (AST Analysis)

↓
Static Analysis + Metrics

↓
LLM Evaluation (LLaMA 3.3)

↓
Scoring Engine

↓
Final Hiring Report

---

### 📊 Output Report

The system generates:

1. Overall Score (0–100)
2. Parameter-wise breakdown
3. File-level evaluation
4. Missing requirements
5. Improvement suggestions
6. Interviewer notes
7. Hiring recommendation:
- Shortlist
- Needs Review
- Reject

---

### 🎯 Use Cases

1. Developer hiring & screening
2. Internship evaluation
3. Hackathon judging
4. Academic project assessment
5. Freelance vetting
