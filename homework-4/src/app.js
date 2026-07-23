const express = require('express');
const { router } = require('./expenses');

// Builds the Express app without starting a listener, so tests can drive it via supertest
// and the entry point (index.js) can attach a real port.
function createApp() {
  const app = express();
  app.use(express.json());
  app.use('/', router);
  return app;
}

module.exports = { createApp };
