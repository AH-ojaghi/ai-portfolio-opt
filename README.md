# AI Portfolio Optimizer 2025 🚀

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11-yellow)
![React](https://img.shields.io/badge/React-18-blue)
![Docker](https://img.shields.io/badge/Docker-Ready-green)
![Status](https://img.shields.io/badge/Status-Production%20Demo-orange)

**A next-generation Robo-Advisor and WealthTech platform powered by Unsupervised Machine Learning.**

This project is a commercial-grade demo of a real-time investment portfolio optimizer. It utilizes **Hierarchical Risk Parity (HRP)** and **Ledoit-Wolf Covariance Shrinkage** to construct robust, diversified portfolios dynamically based on user-selected assets.



## 🌟 Key Features

-   **🤖 AI-Driven Optimization:** Implements Hierarchical Risk Parity (HRP) using Hierarchical Tree Clustering (Unsupervised ML).
-   **⚡ Real-Time Processing:** Calculates optimal weights on-the-fly via a high-performance FastAPI backend.
-   **📉 Advanced Risk Management:** Applies Ledoit-Wolf shrinkage to reduce noise in the covariance matrix.
-   **📊 Interactive Dashboard:** Professional React frontend with Recharts for dynamic visualization and performance backtesting.
-   **🐳 Cloud-Native Architecture:** Fully containerized with Docker & Docker Compose for one-click deployment.

## 🛠 Tech Stack

-   **Backend:** Python 3.11, FastAPI, Riskfolio-lib, Pandas, NumPy, Scikit-learn.
-   **Frontend:** TypeScript, React 18, Vite, Tailwind CSS, Recharts.
-   **DevOps:** Docker, Docker Compose.

## 🚀 Quick Start

You can spin up the entire stack with a single command.

### Prerequisites
-   Docker & Docker Compose installed.

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/AH-ojaghi/ai-portfolio-opt.git
    cd ai-portfolio-opt
    ```

2.  Run the application:
    ```bash
    docker-compose up --build
    ```

3.  Access the dashboard:
    -   Frontend: `http://localhost:3000`
    -   API Docs: `http://localhost:8000/docs`

## 🧠 The AI Engine

Unlike traditional Mean-Variance Optimization (Markowitz), which is sensitive to outliers and correlation noise, this engine uses a 3-step Machine Learning approach:

1.  **Denoising (Ledoit-Wolf):** Mathematically "shrinks" the covariance matrix to filter out noise from historical data.
2.  **Tree Clustering (Unsupervised Learning):** Organizes assets into a hierarchical tree structure based on similarity (correlation distance).
3.  **Recursive Bisection:** Allocates capital top-down through the tree, ensuring genuine diversification across asset clusters.

## 📄 License
MIT License - Created for educational and demo purposes.
