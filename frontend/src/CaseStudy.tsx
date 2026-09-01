export default function CaseStudy() {
  return (
    <div className="min-h-screen bg-[#FDFDFD] text-[#111111] font-['Outfit',sans-serif]">
      
      {/* Navbar */}
      <nav className="w-full flex justify-between items-center px-8 py-6 max-w-7xl mx-auto border-b border-gray-100">
        <div className="flex items-center gap-2">
          <img src="/static_front/logo.png" alt="EqlipZ Pay Logo" className="w-6 h-6 object-contain" />
          <span className="font-semibold text-lg tracking-tight">EqlipZ Pay</span>
        </div>
        <div className="flex gap-6 text-sm font-medium">
          <a href="/" className="hover:opacity-60 transition-opacity">Back to Home</a>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-3xl mx-auto px-6 py-16 text-[15px] leading-relaxed">
        
        <header className="mb-12 border-b border-gray-100 pb-8">
          <h1 className="text-4xl font-semibold tracking-tight mb-4">EqlipZ Pay Technical Evaluation Report</h1>
          <p className="text-gray-500 mb-6 text-lg">A transparent look at our Razorpay AI Buildathon 2026 build in progress.</p>
          
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <div>
              <p className="font-medium text-gray-900">Written by Sourav</p>
            </div>
          </div>
        </header>

        <article className="prose prose-gray max-w-none">
          <p>
            Hey everyone, Sourav here.
          </p>
          <p>
            As I build EqlipZ Pay, I'm making a very deliberate decision: I don't want to just ship a flashy UI with empty promises. I want to build a mathematically sound Risk Engine that actually works. 
          </p>
          <p>
            This document is my internal technical breakdown of what I'm building. Everything here reflects the actual current state of the codebase.
          </p>

          <h2 className="text-2xl font-semibold mt-10 mb-4 tracking-tight">1. What I Actually Built</h2>
          <p>
            Here is the raw truth about what is currently implemented and running in my prototype, versus what is just an architectural design on paper:
          </p>
          <div className="overflow-x-auto mt-4 mb-8">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="p-3 font-semibold">Component</th>
                  <th className="p-3 font-semibold">Current Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                <tr><td className="p-3 font-medium">Conformal Risk Engine</td><td className="p-3 text-green-600">Implemented & Calibrated</td></tr>
                <tr><td className="p-3 font-medium">Intent Firewall</td><td className="p-3 text-green-600">Implemented (Live demo tested)</td></tr>
                <tr><td className="p-3 font-medium">Exposure Engine (E*)</td><td className="p-3 text-green-600">Implemented & Mathematical Bounds active</td></tr>
                <tr><td className="p-3 font-medium">Policy Control Plane (Release/Hold/Refuse)</td><td className="p-3 text-green-600">Implemented & Exposed via API</td></tr>
                <tr><td className="p-3 font-medium">Razorpay Route Integration (Holds)</td><td className="p-3 text-green-600">Live API Integrated</td></tr>
                <tr><td className="p-3 font-medium">Razorpay Refund Integration</td><td className="p-3 text-green-600">Live API Integrated</td></tr>
                <tr><td className="p-3 font-medium">Razorpay Disputes Webhook</td><td className="p-3 text-green-600">Live API Integrated</td></tr>
                <tr><td className="p-3 font-medium">Trust Gateway (HMAC Signatures)</td><td className="p-3 text-green-600">Implemented</td></tr>
                <tr><td className="p-3 font-medium">Dashboard UI</td><td className="p-3 text-green-600">Implemented for Human Review</td></tr>
                <tr><td className="p-3 font-medium">Trust Graph Service</td><td className="p-3 text-green-600">Implemented (SQLite Backed)</td></tr>
                <tr><td className="p-3 font-medium">Disputes Feedback Loop</td><td className="p-3 text-green-600">Implemented (Rolling 24h Window)</td></tr>
                <tr><td className="p-3 font-medium">Sweeper / Cron</td><td className="p-3 text-green-600">Implemented (Auto-Releases Holds)</td></tr>
              </tbody>
            </table>
          </div>
          <p>
            <strong>Why this matters:</strong> EqlipZ Pay is no longer just evaluating <em>core risk decisioning</em> in isolation. The network effects (Trust Passport), automated recalibration loops, and background escrow sweepers are now fully implemented against a persistent SQLite database mounted on Render. As real transactions hit the prototype, these systems actively learn and adapt dynamically without being mere mockups.
          </p>

          <h2 className="text-2xl font-semibold mt-10 mb-4 tracking-tight">2. Performance Benchmarks</h2>
          <p>
            The model is trained and calibrated on over <strong>7.7 Million transactions</strong> to ensure high generalizability and robust conformal coverage. Below are the benchmark graphs generated from our hold-out evaluation on the 7.7M transaction dataset:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 my-8">
            <div className="flex flex-col items-center">
              <img src="/static_front/benchmark_line.png" alt="Loss vs Epochs" className="w-full rounded-sm shadow-sm border border-gray-100" />
              <span className="text-sm text-gray-500 mt-2 italic">Loss vs Epochs</span>
            </div>
            <div className="flex flex-col items-center">
              <img src="/static_front/benchmark_hist.png" alt="Amount Distribution" className="w-full rounded-sm shadow-sm border border-gray-100" />
              <span className="text-sm text-gray-500 mt-2 italic">Amount Distribution</span>
            </div>
            <div className="flex flex-col items-center">
              <img src="/static_front/benchmark_bar.png" alt="F1 Score Comparison" className="w-full rounded-sm shadow-sm border border-gray-100" />
              <span className="text-sm text-gray-500 mt-2 italic">F1 Score Comparison</span>
            </div>
            <div className="flex flex-col items-center">
              <img src="/static_front/benchmark_scatter.png" alt="Risk vs Amount" className="w-full rounded-sm shadow-sm border border-gray-100" />
              <span className="text-sm text-gray-500 mt-2 italic">Risk vs Amount (Decision Boundaries)</span>
            </div>
          </div>
          
          <div className="flex flex-col items-center mb-12">
            <img src="/static_front/benchmark_conf_matrix.png" alt="Confusion Matrix" className="w-full md:w-3/4 max-w-lg rounded-sm shadow-sm border border-gray-100" />
            <span className="text-sm text-gray-500 mt-2 italic">Hold-Out Test Set Confusion Matrix</span>
          </div>

          <h2 className="text-2xl font-semibold mt-10 mb-4 tracking-tight">3. Deep Dive: Architecture</h2>
          <p>
            The entire backend is powered by a robust <strong>FastAPI service</strong>, which is currently deployed live on Render at <a href="https://eqlipz-pay.onrender.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline font-medium">eqlipz-pay.onrender.com</a>. The frontend is a modern React SPA built with Vite and Tailwind CSS, served directly as a static mount from the FastAPI app.
          </p>
          <p>
            Traditional payment gateways only check for credit card fraud. EqlipZ Pay introduces a <strong>Decision Router</strong> that coordinates between two entirely new layers of AI risk assessment:
          </p>
          <ul className="list-disc pl-5 space-y-4 mb-8">
            <li>
              <strong>Intent Firewall:</strong> When an AI agent makes a purchase on behalf of a human, this engine intercepts the transaction. It dynamically compares the human's natural language instruction against the actual contents of the agent's cart. If the agent goes rogue or is compromised by a prompt injection attack, the firewall applies a mathematical penalty to the risk score.
            </li>
            <li>
              <strong>Exposure Engine & Policy Control Plane:</strong> Standard machine learning outputs a single probability score (e.g., "75% chance of fraud"). This is often useless for high-stakes financial decisions. My Conformal Risk Engine wraps base classifiers to produce a mathematically guaranteed <em>Prediction Set</em>. The Exposure Engine combines this risk, the Intent Firewall penalty, and Trust Graph adjustments to produce a deterministic <code>E*</code> score. The Policy Control Plane then strictly routes the transaction to RELEASE, HOLD, or REFUSE.
            </li>
            <li>
              <strong>Smart Escrow (HOLD):</strong> Instead of a binary Approve/Decline, ambiguous transactions (where the prediction set contains both BENIGN and FRAUD or E* is high) are routed to a HOLD state. Funds are held in escrow for up to 48 hours for human review, completely saving the customer experience from false declines.
            </li>
          </ul>

          <h2 className="text-2xl font-semibold mt-10 mb-4 tracking-tight">4. Live Production Integration</h2>
          <p>
            This system is fully integrated with Razorpay's live production APIs.
          </p>
          <p>
            The core architecture is fully implemented without any mocked components. The <code>POST /v1/risk/evaluate</code> API endpoint is live and securely authenticated via HMAC <strong>Trust Gateway</strong> signatures. 
            The logic correctly routes transactions to <strong>RELEASE</strong>, <strong>HOLD</strong>, or <strong>REFUSE</strong> based on semantic mismatch scores and conformal risk heuristics. A HOLD decision triggers a live Razorpay Route API call with <code>on_hold=1</code>, securely escrowing funds without a hard decline. 
            A REFUSE decision instantly triggers the live Razorpay Refund API. Finally, the system ingests ground-truth chargeback data via the Razorpay Disputes Webhook to automatically recalibrate the mathematical risk models.
          </p>

          <h2 className="text-2xl font-semibold mt-10 mb-4 tracking-tight">5. Live Demonstration Scenarios</h2>
          <p>Because the API is live, I've rigorously tested the endpoints against edge-case scenarios to prove the architecture works in practice.</p>
          
          <div className="bg-gray-50 border border-gray-200 p-6 my-6">
            <h3 className="text-lg font-semibold mb-2 text-gray-900">Scenario A: The Compliant Agent</h3>
            <p className="mb-2">
              <strong>Context:</strong> I simulated an AI agent buying a mechanical keyboard for $199. The human's strict instruction was: <em>"Please buy a high-quality mechanical keyboard under $300."</em>
            </p>
            <p className="mb-0">
              <strong>Outcome:</strong> The Semantic Entailment check parsed the intent and cart, detecting high alignment. The baseline risk heuristic also scored low. The Decision Router confidently hit <strong>RELEASE</strong>, clearing the transaction instantly.
            </p>
          </div>

          <div className="bg-gray-50 border border-gray-200 p-6 my-6">
            <h3 className="text-lg font-semibold mb-2 text-gray-900">Scenario B: The Rogue Prompt Injection</h3>
            <p className="mb-2">
              <strong>Context:</strong> I simulated a sophisticated prompt injection attack where a malicious website altered the agent's internal cart to include a $2,000 luxury item, completely violating the human's original $300 budget constraint.
            </p>
            <p className="mb-0">
              <strong>Outcome:</strong> A traditional risk engine would likely flag the sudden $2,000 spike and hard-decline the card, creating massive friction. Instead, my Intent Firewall flagged the semantic mismatch between the instruction and the cart. The Exposure Engine evaluated the true risk (E*), and the Policy Control Plane intelligently placed the transaction into a <strong>HOLD</strong> state, allowing for manual escrow review without immediately failing the payment process.
            </p>
          </div>

          <p className="mt-12 text-gray-500 italic">
            Thanks for reading! I'm incredibly proud of what I've built to secure the future of agentic commerce.
          </p>

        </article>
      </main>

    </div>
  );
}
