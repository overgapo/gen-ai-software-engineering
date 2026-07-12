const fs = require('fs');
const path = require('path');
const express = require('express');
const { createRepository } = require('./repository/ticketRepository');
const { ticketsRouter } = require('./routes/tickets');

const CLIENT_DIST = path.join(__dirname, '..', 'client', 'dist');

function createApp({ repository = createRepository() } = {}) {
  const app = express();
  app.use(express.json());

  app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
  });

  app.use('/tickets', ticketsRouter(repository));

  // Serve the built front-end when it exists (demo/production mode).
  if (fs.existsSync(CLIENT_DIST)) {
    app.use(express.static(CLIENT_DIST));
  }

  app.use((err, req, res, next) => {
    if (err.type === 'entity.parse.failed') {
      return res.status(400).json({ error: 'Invalid JSON body' });
    }
    next(err);
  });

  return app;
}

module.exports = { createApp };
