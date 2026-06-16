# AI Hardware Design Copilot (Vivado Code Generator)

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-blue?style=for-the-badge)](https://vivado-code-generator-git-main-sujithravuri1235.vercel.app/)

## 🌐 Live Deployment
- **Frontend URL:** [https://vivado-code-generator-git-main-sujithravuri1235.vercel.app/](https://vivado-code-generator-git-main-sujithravuri1235.vercel.app/)

##  Project Overview
The **AI Hardware Design Copilot** is a full-stack web application that transforms natural language prompts into verified digital hardware circuits. Acting as an intelligent assistant for FPGA and ASIC engineers, it automatically generates Verilog code, tests it for syntax and synthesis errors using Xilinx Vivado, and visualizes the resulting circuit architecture on a modern frontend dashboard.

##  How it Works (The Flow)
1. **User Input:** A user logs in (via their email) on the React frontend and enters a natural language prompt (e.g., *"Design a 4-bit carry lookahead adder"*).
2. **LangGraph Pipeline:** The FastAPI backend receives the request and triggers an intelligent LangGraph orchestration pipeline.
3. **Code Generation:** The AI processes the prompt, retrieves relevant domain knowledge (RAG), and generates the Verilog implementation and its associated Testbench.
4. **Vivado Validation:** The generated code is locally verified using the Vivado toolchain to ensure synthesizability and timing correctness.
5. **Persistence:** The final generated circuit, including its truth table, boolean equations, and Verilog code, is securely logged to a Supabase PostgreSQL database tied to the user's email.
6. **Frontend Visualization:** The React UI renders the results, showing a beautifully animated Transistor/Gate-level schematic, the truth table, and Vivado compilation reports.

---

##  Getting Started

To run this application locally, you will need to start both the Python backend and the Vite+React frontend in separate terminal windows.

### 1. Start the Backend (FastAPI)
The backend requires Python and relies on Uvicorn to serve the API.

1. Open a terminal and navigate to the project root.
2. Change into the `backend` directory:
   ```bash
   cd backend
   ```
3. *(Optional but recommended)* Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   
   # Windows:
   .venv\Scripts\activate
   
   # Mac/Linux:
   source .venv/bin/activate
   ```
4. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the FastAPI development server:
   ```bash
   python -m uvicorn app.main:app --reload
   ```
*The backend API will now be running and accessible at `http://localhost:8000`.*

### 2. Start the Frontend (React + Vite)
The frontend uses Vite for blazing fast development and hot-module replacement.

1. Open a **new** terminal and navigate to the project root.
2. Change into the `frontend` directory:
   ```bash
   cd frontend
   ```
3. Install the Node.js dependencies:
   ```bash
   npm install
   ```
4. Start the development server:
   ```bash
   npm run dev
   ```
*The frontend application will now be accessible at `http://localhost:5173`. Open this URL in your browser to interact with the Copilot!*

---

##  Tech Stack
- **Frontend:** React, Vite, TailwindCSS, React Flow
- **Backend:** Python, FastAPI, LangGraph Orchestration
- **AI/LLM:** Grok API
- **Hardware Validation:** Xilinx Vivado (Locally installed)
- **Database:** Supabase (PostgreSQL)
