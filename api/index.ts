import express, { Request, Response } from 'express';
import cors from 'cors';
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.get('/api/health', (req: Request, res: Response) => {
  res.json({ status: 'OK', message: 'Looky Backend is running' });
});

app.get('/api/items', (req: Request, res: Response) => {
  res.json({ items: [] });
});

// Export for Vercel
export default app;

// For local development
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
  });
}
