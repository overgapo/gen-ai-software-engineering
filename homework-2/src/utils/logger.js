// Structured JSON application log. Silent under test to keep output clean.
function logEvent(event, fields) {
  if (process.env.NODE_ENV === 'test') return;
  console.log(JSON.stringify({ event, timestamp: new Date().toISOString(), ...fields }));
}

module.exports = { logEvent };
