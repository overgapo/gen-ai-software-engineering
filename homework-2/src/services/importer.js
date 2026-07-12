const { parse: parseCsvSync } = require('csv-parse/sync');
const { XMLParser, XMLValidator } = require('fast-xml-parser');
const { validateCreate } = require('../validation/ticket');
const { buildTicket } = require('./ticketService');
const { classifyTicket } = require('./classifier');
const { logEvent } = require('../utils/logger');

function detectFormat(filename, mimetype) {
  const ext = (filename || '').toLowerCase().split('.').pop();
  if (['csv', 'json', 'xml'].includes(ext)) return ext;
  const mime = (mimetype || '').toLowerCase();
  if (mime.includes('csv')) return 'csv';
  if (mime.includes('json')) return 'json';
  if (mime.includes('xml')) return 'xml';
  return null;
}

// CSV: one ticket per row; `tags` and `metadata` cells contain JSON strings.
function parseCsv(content) {
  const rows = parseCsvSync(content, {
    columns: true,
    skip_empty_lines: true,
    trim: true,
  });
  return rows.map((row) => {
    const record = {};
    for (const [key, raw] of Object.entries(row)) {
      if (raw === '') continue;
      if (key === 'tags' || key === 'metadata') {
        try {
          record[key] = JSON.parse(raw);
        } catch {
          // leave the raw string so validation reports it on the right field
          record[key] = raw;
        }
      } else {
        record[key] = raw;
      }
    }
    return record;
  });
}

function parseJson(content) {
  const data = JSON.parse(content);
  if (!Array.isArray(data)) {
    throw new Error('JSON import must be an array of ticket objects');
  }
  return data;
}

function parseXml(content) {
  const validation = XMLValidator.validate(content);
  if (validation !== true) {
    throw new Error(`invalid XML: ${validation.err.msg}`);
  }
  const parser = new XMLParser({
    parseTagValue: false,
    isArray: (name, jpath) =>
      jpath === 'tickets.ticket' || jpath === 'tickets.ticket.tags.tag',
  });
  const doc = parser.parse(content);
  const tickets = doc && doc.tickets && doc.tickets.ticket;
  if (!tickets) {
    throw new Error('XML must contain <tickets> with <ticket> elements');
  }
  return tickets.map((t) => {
    const record = { ...t };
    if ('tags' in record) {
      record.tags = t.tags && t.tags.tag ? t.tags.tag : [];
    }
    if (record.metadata === '') delete record.metadata;
    return record;
  });
}

const PARSERS = { csv: parseCsv, json: parseJson, xml: parseXml };

// All-or-nothing import (SPEC §4): validate every record first; persist
// only when there are zero errors.
function importTickets(buffer, format, { repository, autoClassify = false }) {
  let records;
  try {
    records = PARSERS[format](buffer.toString('utf8'));
  } catch (err) {
    return { ok: false, fileError: err.message };
  }
  if (records.length === 0) {
    return { ok: false, fileError: 'file contains no records' };
  }

  const errors = [];
  const valids = [];
  records.forEach((record, index) => {
    const { errors: recordErrors, value } = validateCreate(record);
    if (recordErrors.length) {
      errors.push({ record: index + 1, details: recordErrors });
    } else {
      valids.push(value);
    }
  });

  if (errors.length) {
    const summary = {
      total: records.length,
      successful: 0,
      failed: errors.length,
      errors,
    };
    logEvent('import_rejected', { format, ...summary, errors: undefined });
    return { ok: false, summary };
  }

  const tickets = valids.map((value) => {
    let ticket = buildTicket(value);
    if (autoClassify) {
      ticket = classifyTicket(ticket, {
        applyCategory: value.category === undefined,
        applyPriority: value.priority === undefined,
      });
    }
    return ticket;
  });
  repository.createMany(tickets);

  const summary = {
    total: records.length,
    successful: tickets.length,
    failed: 0,
    errors: [],
  };
  logEvent('import_completed', { format, autoClassify, ...summary, errors: undefined });
  return { ok: true, summary };
}

module.exports = { detectFormat, importTickets };
