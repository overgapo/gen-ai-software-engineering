const express = require('express');
const multer = require('multer');
const { validateCreate, validateUpdate } = require('../validation/ticket');
const { buildTicket, applyUpdate } = require('../services/ticketService');
const { classifyTicket } = require('../services/classifier');
const { detectFormat, importTickets } = require('../services/importer');
const { CATEGORIES, PRIORITIES, STATUSES } = require('../config/enums');

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
});

const FILTER_ENUMS = {
  category: CATEGORIES,
  priority: PRIORITIES,
  status: STATUSES,
};

function validateFilters(query) {
  const errors = [];
  for (const [field, allowed] of Object.entries(FILTER_ENUMS)) {
    if (query[field] !== undefined && !allowed.includes(query[field])) {
      errors.push({ field, message: `must be one of: ${allowed.join(', ')}` });
    }
  }
  return errors;
}

function ticketsRouter(repository) {
  const router = express.Router();

  router.post('/', (req, res) => {
    const { errors, value } = validateCreate(req.body);
    if (errors.length) {
      return res.status(400).json({ error: 'Validation failed', details: errors });
    }
    let ticket = buildTicket(value);
    if (req.query.auto_classify === 'true') {
      ticket = classifyTicket(ticket, {
        applyCategory: value.category === undefined,
        applyPriority: value.priority === undefined,
      });
    }
    res.status(201).json(repository.create(ticket));
  });

  router.post('/import', upload.single('file'), (req, res) => {
    if (!req.file) {
      return res
        .status(400)
        .json({ error: 'No file uploaded; expected multipart field "file"' });
    }
    const format = detectFormat(req.file.originalname, req.file.mimetype);
    if (!format) {
      return res
        .status(400)
        .json({ error: 'Unsupported file format; expected .csv, .json or .xml' });
    }
    const autoClassify =
      req.query.auto_classify === 'true' ||
      (req.body && req.body.auto_classify === 'true');
    const result = importTickets(req.file.buffer, format, {
      repository,
      autoClassify,
    });
    if (result.fileError) {
      return res.status(400).json({ error: 'Import failed', reason: result.fileError });
    }
    if (!result.ok) {
      return res.status(400).json({ error: 'Import failed', ...result.summary });
    }
    res.status(201).json(result.summary);
  });

  router.post('/:id/auto-classify', (req, res) => {
    const existing = repository.getById(req.params.id);
    if (!existing) return res.status(404).json({ error: 'Ticket not found' });
    const classified = {
      ...classifyTicket(existing),
      updated_at: new Date().toISOString(),
    };
    res.json(repository.update(existing.id, classified));
  });

  router.get('/', (req, res) => {
    const errors = validateFilters(req.query);
    if (errors.length) {
      return res.status(400).json({ error: 'Validation failed', details: errors });
    }
    const { category, priority, status, assigned_to, customer_id, search } = req.query;
    res.json(repository.list({ category, priority, status, assigned_to, customer_id, search }));
  });

  router.get('/:id', (req, res) => {
    const ticket = repository.getById(req.params.id);
    if (!ticket) return res.status(404).json({ error: 'Ticket not found' });
    res.json(ticket);
  });

  router.put('/:id', (req, res) => {
    const existing = repository.getById(req.params.id);
    if (!existing) return res.status(404).json({ error: 'Ticket not found' });
    const { errors, value } = validateUpdate(req.body);
    if (errors.length) {
      return res.status(400).json({ error: 'Validation failed', details: errors });
    }
    res.json(repository.update(existing.id, applyUpdate(existing, value)));
  });

  router.delete('/:id', (req, res) => {
    if (!repository.delete(req.params.id)) {
      return res.status(404).json({ error: 'Ticket not found' });
    }
    res.status(204).end();
  });

  return router;
}

module.exports = { ticketsRouter };
