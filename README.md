# AI Scalping Trading Dashboard

A modern React-based dashboard for high-frequency forex scalping trading with AI-powered market analysis.

## Features

- 📊 **Real-time Dashboard**: Live trading metrics, positions, and performance tracking
- 🤖 **AI Market Analysis**: Gemini-powered insights for EUR/USD, GBP/USD, and USD/JPY
- ⚙️ **Trading Settings**: Configurable parameters for lot sizes, risk management, and API connections
- 📱 **Responsive Design**: Optimized for desktop and mobile devices
- 🔄 **Live Data Streaming**: Server-sent events for real-time updates

## Tech Stack

- **Frontend**: React 18, TypeScript, Tailwind CSS
- **AI Integration**: Google Gemini API
- **Build Tool**: Create React App
- **Deployment**: Netlify (static hosting)
- **Backend**: Flask API on Render
- **Database**: PostgreSQL on Render

## Quick Start

### Prerequisites
- Node.js 18+
- npm or yarn

### Installation

```bash
# Clone the repository
git clone https://github.com/inaradesignskochi/MT4_AI_HFS.git
cd money

# Install dependencies
npm install

# Start development server
npm start
```

### Build for Production

```bash
npm run build
```

## Deployment

### Frontend (Netlify)
The frontend is automatically deployed to Netlify when code is pushed to the main branch.

**Live URL:** https://super-halva-7f98bf.netlify.app/

### Backend (Render)
The backend is deployed on Render and provides the following API endpoints:

#### Health Check
```bash
curl https://ai-trading-backend-m1k7.onrender.com/api/health
```

#### API Endpoints
- `GET /api/health` - Health check
- `POST /api/ticks` - Receive tick data from MT4
- `GET /api/signals` - Get trading signals for MT4
- `POST /api/trades` - Log executed trades
- `GET /api/dashboard/stream` - Real-time dashboard data (SSE)

## Configuration

### Frontend Settings
Access the Settings page in the deployed app to configure:

```
GCP VM IP: https://ai-trading-backend-m1k7.onrender.com
Backend API Key: production
Gemini API Key: AIzaSyBoHx9EG1ff7Hfb5XQwn1sHQMquHZp9z_g
Lot Size: 0.01
Max Positions: 3
Max Daily Loss: 50
Max Spread Pips: 2.0
Tick Batch Size: 500
Signal Poll Interval Ms: 500
```

## MT4 Integration

### Download Expert Advisor
```
https://raw.githubusercontent.com/inaradesignskochi/MT4_AI_HFS/main/mt4/Expert%20Advisor.mq4
```

### MT4 Configuration
1. **Tools → Options → Expert Advisors**
2. ✅ Allow automated trading
3. ✅ Allow WebRequest for: `https://ai-trading-backend-m1k7.onrender.com`
4. **Attach EA to EURUSD chart**
5. **Set EnableTrading: false** first for testing

## Docker

### Build and Run
```bash
# Build image
docker build -t ai-trading-frontend .

# Run container
docker run -p 3000:80 ai-trading-frontend
```

## Testing API Endpoints

### Using curl (Windows PowerShell)
```powershell
# Health check
curl -Uri "https://ai-trading-backend-m1k7.onrender.com/api/health"

# Test with headers
$headers = @{"Content-Type" = "application/json"}
$body = '{"ticks": [{"timestamp": 1234567890, "bid": 1.0500, "ask": 1.0502, "spread": 2, "volume": 100}], "symbol": "EURUSD"}'
Invoke-WebRequest -Uri "https://ai-trading-backend-m1k7.onrender.com/api/ticks" -Method POST -Headers $headers -Body $body
```

### Using JavaScript (Browser Console)
```javascript
// Health check
fetch('https://ai-trading-backend-m1k7.onrender.com/api/health')
  .then(r => r.json())
  .then(d => console.log(d));

// Test tick data
fetch('https://ai-trading-backend-m1k7.onrender.com/api/ticks', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    ticks: [{timestamp: Date.now(), bid: 1.0500, ask: 1.0502, spread: 2, volume: 100}],
    symbol: 'EURUSD'
  })
}).then(r => r.json()).then(d => console.log(d));
```

## Project Structure

```
money/
├── public/
│   ├── index.html
│   └── _redirects
├── src/
│   ├── components/
│   │   ├── Dashboard.tsx
│   │   ├── Header.tsx
│   │   ├── Settings.tsx
│   │   └── ...
│   ├── hooks/
│   │   ├── useSettings.ts
│   │   └── useTradingData.ts
│   ├── services/
│   │   └── geminiService.ts
│   ├── types.ts
│   ├── App.tsx
│   └── index.tsx
├── mt4/
│   └── Expert Advisor.mq4
├── Dockerfile
├── netlify.toml
├── package.json
└── README.md
```

## Security

- API keys are stored securely in browser localStorage
- Backend validates all incoming requests
- CORS is properly configured for frontend-backend communication
- Input validation prevents injection attacks

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `npm test`
5. Submit a pull request

## License

MIT License - see LICENSE file for details