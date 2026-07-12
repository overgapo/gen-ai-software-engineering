const {
  CATEGORY_KEYWORDS,
  REPRO_MARKERS,
  NUMBERED_STEPS_RE,
  PRIORITY_KEYWORDS,
  PRIORITY_ORDER,
} = require('../config/classificationRules');
const { logEvent } = require('../utils/logger');

const CONFIDENCE_MIN = 0.3;
const CONFIDENCE_MAX = 0.95;
const CONFIDENCE_OTHER = 0.2;

function findMatches(text, keywords) {
  return keywords.filter((kw) => text.includes(kw));
}

function classifyCategory(text) {
  const matchesByCategory = {};
  for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    matchesByCategory[category] = findMatches(text, keywords);
  }

  const reproMatches = findMatches(text, REPRO_MARKERS);
  if (NUMBERED_STEPS_RE.test(text)) reproMatches.push('numbered steps');

  // bug_report = technical-issue evidence upgraded by reproduction markers.
  if (reproMatches.length > 0) {
    matchesByCategory.bug_report = [
      ...matchesByCategory.technical_issue,
      ...reproMatches,
    ];
    matchesByCategory.technical_issue = [];
  }

  let winner = 'other';
  let winnerMatches = [];
  for (const [category, matches] of Object.entries(matchesByCategory)) {
    if (matches.length > winnerMatches.length) {
      winner = category;
      winnerMatches = matches;
    }
  }

  const competing = Object.entries(matchesByCategory)
    .filter(([category]) => category !== winner)
    .reduce((sum, [, matches]) => sum + matches.length, 0);

  const confidence =
    winner === 'other'
      ? CONFIDENCE_OTHER
      : Math.min(
          CONFIDENCE_MAX,
          Math.max(
            CONFIDENCE_MIN,
            winnerMatches.length / (winnerMatches.length + competing)
          )
        );

  return { category: winner, keywords: winnerMatches, confidence };
}

function classifyPriority(text) {
  const matchesByLevel = {};
  for (const [level, keywords] of Object.entries(PRIORITY_KEYWORDS)) {
    matchesByLevel[level] = findMatches(text, keywords);
  }

  let winner = 'medium';
  let winnerMatches = [];
  for (const level of PRIORITY_ORDER) {
    // strictly more matches wins; ties resolve to the higher level,
    // which PRIORITY_ORDER visits first
    if (matchesByLevel[level].length > winnerMatches.length) {
      winner = level;
      winnerMatches = matchesByLevel[level];
    }
  }

  return { priority: winner, keywords: winnerMatches };
}

function classify(ticket) {
  const text = `${ticket.subject}\n${ticket.description}`.toLowerCase();

  const categoryResult = classifyCategory(text);
  const priorityResult = classifyPriority(text);

  const reasoningParts = [
    categoryResult.category === 'other'
      ? 'no category keywords matched'
      : `category "${categoryResult.category}": matched ${categoryResult.keywords
          .map((k) => `"${k}"`)
          .join(', ')}`,
    priorityResult.priority === 'medium'
      ? 'priority "medium": no priority keywords matched (default)'
      : `priority "${priorityResult.priority}": matched ${priorityResult.keywords
          .map((k) => `"${k}"`)
          .join(', ')}`,
  ];

  return {
    category: categoryResult.category,
    priority: priorityResult.priority,
    confidence: Number(categoryResult.confidence.toFixed(2)),
    reasoning: reasoningParts.join('; '),
    keywords: [...categoryResult.keywords, ...priorityResult.keywords],
  };
}

// Classifies a ticket and returns the updated ticket object.
// Manual wins per field: when applyCategory/applyPriority is false the
// client-supplied value is kept, the result is still recorded in
// `classification`, and overridden is set to true.
function classifyTicket(ticket, { applyCategory = true, applyPriority = true } = {}) {
  const result = classify(ticket);
  const classification = {
    ...result,
    classified_at: new Date().toISOString(),
    overridden: !applyCategory || !applyPriority,
  };

  logEvent('classification', {
    ticket_id: ticket.id,
    applied: { category: applyCategory, priority: applyPriority },
    category: result.category,
    priority: result.priority,
    confidence: result.confidence,
    keywords: result.keywords,
  });

  return {
    ...ticket,
    ...(applyCategory ? { category: result.category } : {}),
    ...(applyPriority ? { priority: result.priority } : {}),
    classification,
  };
}

module.exports = { classify, classifyTicket };
