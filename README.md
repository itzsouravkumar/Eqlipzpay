# EqlipZ Pay

**A Trust Layer for Payments Made by Humans and AI Agents**

EqlipZ Pay operates as risk and trust middleware for digital payments. Designed specifically to integrate with Razorpay Route and emerging AI agent protocols (AP2, UCP, MCP), the system mitigates settlement risk by introducing a reversible, mathematically bounded "Hold" state for ambiguous transactions. Rather than forcing a binary approve/decline decision, EqlipZ Pay holds funds for a maximum of 48 hours while maintaining rigorous statistical guarantees on accuracy.

This project is built for robustness, modularity, and rapid deployment in production environments.

---

## System Architecture

EqlipZ Pay is composed of highly decoupled services that intercept and evaluate incoming payment authorizations before they reach the final settlement layer.

- **Ingestion Gateway**: Receives incoming webhooks from Razorpay and proxies Model Context Protocol (MCP) tool calls from autonomous AI agents.
- **Conformal Risk Engine**: Applies conformal prediction methodologies to generate statistically bounded confidence sets around existing risk scores (e.g., Razorpay Vulcan).
- **Semantic Entailment Engine**: Validates AI agent intent by checking signed shopping carts against the user's original request parameters.
- **Decision Router**: Synthesizes inputs to emit a definitive action: `Release`, `Refuse`, or `Hold`.
- **Calibration Feedback Loop**: Continuously ingests outcomes from the Razorpay Disputes API to adjust decision thresholds, ensuring the statistical guarantee remains robust against drift.
- **Sweeper**: A reconciliation daemon that polls for missed webhooks or dropped state transitions.

## Project Structure

```text
eqlipz-pay/
├── actions/             # Executes idempotent state changes (Transfers, Refunds, Disputes)
├── config/              # Environment configurations and threshold limits
├── docs/                # Architecture research and product requirement documents
├── flywheel/            # Continuous calibration and Trust Passport generation
├── ingestion/           # Webhook ingestion and MCP tool proxying
├── risk_kernel/         # Core prediction, conformal scoring, and semantic evaluation
├── sweeper/             # Daemon for reconciliation and polling
├── tests/               # Automated integration and unit tests
├── main.py              # Application entry point (FastAPI)
├── render.yaml          # Render deployment specification
└── requirements.txt     # Python dependencies
```

## Deployment

EqlipZ Pay is containerized and configured for straightforward deployment on cloud platforms. The primary deployment target is Render.

### Prerequisites

- Python 3.10+
- Razorpay API Credentials
- Render Account

### Local Development Environment

1. **Clone the repository and configure the virtual environment:**
   ```bash
   git clone <repository_url>
   cd eqlipz-pay
   python -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Ensure `config/razorpay_keys.env` is populated with the necessary API keys and secrets. (Note: Do not commit this file to version control).

4. **Initialize the Server:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 10000 --reload
   ```

### Production Deployment via Render

The repository includes a `render.yaml` specification for Infrastructure as Code (IaC) deployment on Render.

1. Connect your repository to your Render account.
2. Render will automatically detect the `render.yaml` file and provision the web service.
3. Configure your production environment variables (e.g., `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`) securely within the Render dashboard.
4. The service will build dependencies from `requirements.txt` and launch via `uvicorn`.

## Escrow Mechanics and Data Flow

EqlipZ Pay handles state transitions securely and idempotently:

1. **Observation**: A webhook event (`payment.authorized`) or an MCP proxy event is received.
2. **Analysis**: The event is passed through the risk and semantic engines.
3. **Decisioning**:
   - **Benign Only**: Executes an immediate release via a Razorpay Route transfer.
   - **Fraud Only**: Immediately issues a refund and blocks the transaction.
   - **Ambiguous**: Places a temporary escrow hold on the transfer (`on_hold: true`).
4. **Resolution**: Held transactions await manual review or automatic timeout at 48 hours, defaulting to a safe release to prevent indefinite vendor fund locking.

## Reliability and Idempotency

All write operations to the Razorpay API utilize the unique payment ID as an idempotency key. This ensures that network timeouts, webhook retries, or execution interruptions do not result in duplicate transfers or duplicated refund operations.

---

*Confidential - Developed for the Razorpay AI Buildathon 2026.*
