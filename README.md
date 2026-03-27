# Looky Backend

Express.js backend for Looky application, deployed on Vercel.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file:
```bash
cp .env.example .env
```

3. Run locally:
```bash
npm run dev
```

## Deployment

Deploy to Vercel:
```bash
vercel --prod
```

## API Endpoints

- `GET /api/health` - Health check
- `GET /api/items` - Get items
