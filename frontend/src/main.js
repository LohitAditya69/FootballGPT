import './styles.css';

const API_PATH = '/api/v1/ask';
const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const UEFA_REPORTS_URL = 'https://www.uefa.com/news-media/publications/technical-reports/';
const STORE_KEY = 'footballgpt-api-base-url';

const form = document.querySelector('#ask-form');
const questionInput = document.querySelector('#question');
const matchInput = document.querySelector('#match-id');
const triggerInput = document.querySelector('#trigger-event-id');
const apiInput = document.querySelector('#api-base-url');
const charCount = document.querySelector('#char-count');
const questionError = document.querySelector('#question-error');
const requestStatus = document.querySelector('#request-status');
const submitButton = document.querySelector('#submit-button');
const results = document.querySelector('#results');
const resultContent = document.querySelector('#result-content');
const responseBadge = document.querySelector('#response-badge');

apiInput.value = localStorage.getItem(STORE_KEY) || DEFAULT_API_BASE;

function node(tag, className, content) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content !== undefined && content !== null) element.textContent = String(content);
  return element;
}

function append(parent, child) {
  if (child) parent.append(child);
  return parent;
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return 'Not provided';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function showBadge(label, kind = 'muted') {
  responseBadge.textContent = label;
  responseBadge.className = `response-badge badge-${kind}`;
}

function showError(title, message, status = '') {
  resultContent.replaceChildren();
  const box = node('div', 'error-state');
  append(box, node('span', 'error-icon', '!'));
  const copy = node('div', 'error-copy');
  append(copy, node('h3', '', title));
  append(copy, node('p', '', message));
  append(box, copy);
  resultContent.append(box);
  showBadge('Needs attention', 'error');
  requestStatus.textContent = status || title;
}

function validationMessage(value) {
  const question = value.trim();
  if (!question) return 'Enter a question before requesting a review.';
  if (Array.from(question).length > 2000) return 'Questions must be 2,000 characters or fewer.';
  return '';
}

function validateResponse(payload) {
  const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
  const requiredString = (value) => typeof value === 'string' && value.trim().length > 0;

  if (!isRecord(payload) || payload.schema_version !== 'footballgpt-response-v1') return false;
  if (!requiredString(payload.request_id) || !requiredString(payload.answer)) return false;
  if (!['answered', 'abstained'].includes(payload.status)) return false;
  if (!['conditional', 'not_covered', 'unknown'].includes(payload.support_status)) return false;
  if (!['extractive_evidence_brief', 'abstain'].includes(payload.answer_mode)) return false;
  if (!Array.isArray(payload.tactical_passages) || !Array.isArray(payload.historical_examples) || !Array.isArray(payload.limitations)) return false;
  if (payload.event_evidence !== null && !isRecord(payload.event_evidence)) return false;
  if (payload.provenance !== null && !isRecord(payload.provenance)) return false;
  if (payload.status === 'abstained' && (payload.answer_mode !== 'abstain' || payload.tactical_passages.length !== 0)) return false;
  if (payload.status === 'answered' && payload.answer_mode !== 'extractive_evidence_brief') return false;
  if (!payload.tactical_passages.every((item) => isRecord(item) && requiredString(item.evidence_id) && requiredString(item.source_id) && requiredString(item.source_title) && Number.isInteger(item.page) && requiredString(item.citation) && requiredString(item.excerpt) && typeof item.score === 'number' && Number.isFinite(item.score))) return false;
  if (!payload.historical_examples.every((item) => isRecord(item) && requiredString(item.evidence_id) && requiredString(item.match_id) && requiredString(item.source_split) && requiredString(item.label) && typeof item.historical_score === 'number' && Number.isFinite(item.historical_score))) return false;
  if (!payload.limitations.every((item) => typeof item === 'string')) return false;
  if (payload.event_evidence && (!Array.isArray(payload.event_evidence.events) || !requiredString(payload.event_evidence.evidence_id) || !requiredString(payload.event_evidence.match_id) || !requiredString(payload.event_evidence.trigger_event_id) || !requiredString(payload.event_evidence.trigger_event_type) || !requiredString(payload.event_evidence.trigger_timestamp) || !requiredString(payload.event_evidence.window_rule) || !payload.event_evidence.events.every(isRecord))) return false;
  if (payload.provenance && (payload.provenance.schema_version !== 'rgg-provenance-v1' || !Array.isArray(payload.provenance.nodes) || !Array.isArray(payload.provenance.edges) || !payload.provenance.nodes.every(isRecord) || !payload.provenance.edges.every(isRecord))) return false;
  return true;
}

function section(title, overline, className = '') {
  const wrapper = node('section', `evidence-section ${className}`.trim());
  const heading = node('div', 'evidence-section-heading');
  append(heading, node('p', 'eyebrow', overline));
  append(heading, node('h3', '', title));
  append(wrapper, heading);
  return wrapper;
}

function detailRow(label, value, parent) {
  if (value === null || value === undefined || value === '') return;
  const row = node('div', 'detail-row');
  append(row, node('span', 'detail-label', label));
  const display = typeof value === 'object' ? node('pre', 'detail-value code-value', formatValue(value)) : node('span', 'detail-value', value);
  append(row, display);
  parent.append(row);
}

function renderPassages(response, preview) {
  const block = section('UEFA source passages', 'TACTICAL REFERENCE', 'source-section');
  const passages = response.tactical_passages;
  if (!passages.length) {
    append(block, node('p', 'section-empty', response.status === 'abstained'
      ? 'No page-cited UEFA passages were returned for this response.'
      : 'The API returned no page-cited UEFA passages. This response is not shown as supported by source evidence.'));
    return block;
  }

  for (const passage of passages) {
    const card = node('article', 'passage-card');
    const meta = node('div', 'passage-meta');
    const citationLink = node(preview ? 'span' : 'a', 'citation-link', passage.citation);
    if (!preview) {
      citationLink.href = UEFA_REPORTS_URL;
      citationLink.target = '_blank';
      citationLink.rel = 'noopener noreferrer';
      citationLink.setAttribute('aria-label', `${passage.source_title}, page ${passage.page}, opens UEFA technical reports in a new tab`);
    }
    append(meta, citationLink);
    append(meta, node('span', 'passage-id', passage.evidence_id));
    append(card, meta);
    append(card, node('h4', 'passage-title', passage.source_title));
    const excerpt = node('blockquote', 'excerpt', `“${passage.excerpt}”`);
    append(card, excerpt);
    detailRow('Source ID', passage.source_id, card);
    detailRow('Page', passage.page, card);
    detailRow('Evidence ID', passage.evidence_id, card);
    block.append(card);
  }
  return block;
}

function renderEventEvidence(eventEvidence) {
  const block = section('Recorded match events', 'STATSBOMB EVENT WINDOW', 'event-section');
  if (!eventEvidence) {
    append(block, node('p', 'section-empty', 'No supported event window was returned. Event context is not inferred by the frontend.'));
    return block;
  }
  const summary = node('div', 'event-summary');
  detailRow('Match', eventEvidence.match_id, summary);
  detailRow('Trigger', eventEvidence.trigger_event_type, summary);
  detailRow('Timestamp', eventEvidence.trigger_timestamp, summary);
  detailRow('Trigger event ID', eventEvidence.trigger_event_id, summary);
  detailRow('Window rule', eventEvidence.window_rule, summary);
  append(block, summary);
  const events = Array.isArray(eventEvidence.events) ? eventEvidence.events : [];
  append(block, node('p', 'event-count', `${events.length} recorded event${events.length === 1 ? '' : 's'} in this returned window`));
  for (const [index, event] of events.entries()) {
    const details = document.createElement('details');
    details.className = 'data-details event-record';
    const summaryLine = document.createElement('summary');
    summaryLine.textContent = event && typeof event === 'object'
      ? `${event.type || event.event_type || event.name || 'Event'} · ${event.timestamp || event.minute || `Record ${index + 1}`}`
      : `Record ${index + 1}`;
    details.append(summaryLine);
    append(details, node('pre', 'json-block', formatValue(event)));
    block.append(details);
  }
  append(block, node('p', 'evidence-caveat', 'These are recorded event data. They do not establish off-ball runs, team shape, or unseen video context.'));
  return block;
}

function renderHistoricalExamples(examples) {
  const block = section('Historical event examples', 'SIMILAR RECORDED SITUATIONS', 'historical-section');
  if (!examples.length) {
    append(block, node('p', 'section-empty', 'No historical event examples were returned for this question.'));
    return block;
  }
  append(block, node('p', 'evidence-caveat', 'Historical event records are examples, not UEFA principles or coaching ground truth.'));
  for (const example of examples) {
    const card = node('article', 'historical-card');
    append(card, node('p', 'historical-label', example.label || 'Historical event example'));
    const titleParts = [example.team, example.opponent ? `vs ${example.opponent}` : null].filter(Boolean);
    append(card, node('h4', '', titleParts.length ? titleParts.join(' ') : `Match ${example.match_id || 'record'}`));
    detailRow('Match ID', example.match_id, card);
    detailRow('Timestamp', example.timestamp, card);
    detailRow('Event', example.event_type, card);
    detailRow('Play pattern', example.play_pattern, card);
    detailRow('Formation', example.formation, card);
    detailRow('Similarity score', example.historical_score, card);
    detailRow('Source split', example.source_split, card);
    block.append(card);
  }
  return block;
}

function renderProvenance(provenance) {
  const block = section('Provenance', 'HOW THIS RESPONSE WAS ASSEMBLED', 'provenance-section');
  if (!provenance) {
    append(block, node('p', 'section-empty', 'Provenance was not returned. Check the limitations below for the API explanation.'));
    return block;
  }
  const summary = node('div', 'provenance-counts');
  const nodes = Array.isArray(provenance.nodes) ? provenance.nodes : [];
  const edges = Array.isArray(provenance.edges) ? provenance.edges : [];
  append(summary, node('span', '', `${nodes.length} node${nodes.length === 1 ? '' : 's'}`));
  append(summary, node('span', '', `${edges.length} link${edges.length === 1 ? '' : 's'}`));
  append(block, summary);
  if (nodes.length) {
    const list = node('ul', 'provenance-list');
    for (const item of nodes) {
      const li = node('li', '');
      append(li, node('span', 'node-type', item.node_type || 'Node'));
      append(li, node('span', 'node-id', item.id || 'Identifier not provided'));
      list.append(li);
    }
    block.append(list);
  }
  if (edges.length) {
    const list = node('ul', 'provenance-list edge-list');
    for (const item of edges) {
      const li = node('li', '');
      append(li, node('span', 'node-type', item.relation || 'Relation'));
      append(li, node('span', 'node-id', `${item.source || '—'} → ${item.target || '—'}`));
      list.append(li);
    }
    block.append(list);
  }
  const disclosure = document.createElement('details');
  disclosure.className = 'data-details provenance-raw';
  const summaryLine = document.createElement('summary');
  summaryLine.textContent = 'View full provenance data';
  disclosure.append(summaryLine);
  append(disclosure, node('pre', 'json-block', formatValue(provenance)));
  block.append(disclosure);
  return block;
}

function renderLimitations(limitations) {
  const block = section('Limitations', 'READ WITH CONTEXT', 'limitations-section');
  if (!limitations.length) {
    append(block, node('p', 'section-empty', 'The API did not return limitations for this response.'));
    return block;
  }
  const list = node('ul', 'limitations-list');
  for (const limitation of limitations) append(list, node('li', '', limitation));
  block.append(list);
  return block;
}

function renderResponse(response, { preview = false } = {}) {
  resultContent.replaceChildren();
  if (preview) append(resultContent, node('div', 'preview-banner', 'SYNTHETIC UI PREVIEW · Not an API response or real evidence'));
  const intro = node('div', `answer-card ${response.status === 'abstained' ? 'answer-abstained' : ''}`);
  const tag = response.status === 'abstained' ? 'ABSTENTION' : 'EVIDENCE BRIEF';
  append(intro, node('div', 'answer-tag', tag));
  append(intro, node('p', 'answer-text', response.answer));

  const facts = node('div', 'response-facts');
  const statusClass = response.status === 'abstained' ? 'fact-abstained' : 'fact-answered';
  append(facts, node('span', `fact-pill ${statusClass}`, response.status === 'abstained' ? 'Abstained' : 'Answered'));
  const supportLabel = response.support_status.replaceAll('_', ' ');
  append(facts, node('span', 'fact-pill', `Support: ${supportLabel}`));
  append(facts, node('span', 'request-id', `Request ${response.request_id}`));
  intro.append(facts);
  resultContent.append(intro);

  if (response.status === 'answered' && response.tactical_passages.length === 0) {
    append(resultContent, node('div', 'notice-box', 'No tactical passage was returned. This response is not presented as supported by UEFA source evidence.'));
  }
  resultContent.append(renderPassages(response, preview));
  resultContent.append(renderEventEvidence(response.event_evidence));
  resultContent.append(renderHistoricalExamples(response.historical_examples));
  resultContent.append(renderProvenance(response.provenance));
  resultContent.append(renderLimitations(response.limitations));

  showBadge(response.status === 'abstained' ? 'Abstained' : 'Response received', response.status === 'abstained' ? 'warning' : 'success');
  requestStatus.textContent = response.status === 'abstained'
    ? 'The backend abstained. No tactical passages are shown as evidence.'
    : 'Response received. Review the source passages, event records, examples, and limitations separately.';
}

function makePreviewTools() {
  if (!import.meta.env.DEV) return;
  const container = document.querySelector('#preview-tools');
  if (!container) return;
  container.hidden = false;
  const details = document.createElement('details');
  details.className = 'preview-details';
  const summary = document.createElement('summary');
  summary.textContent = 'Preview interface states';
  details.append(summary);
  append(details, node('p', 'preview-note', 'Synthetic previews check layout and error handling only; they are not returned evidence.'));
  const controls = node('div', 'preview-buttons');
  const options = [
    ['answered', 'Answered'],
    ['abstained', 'Abstention'],
    ['service', 'Service error'],
    ['network', 'Network error'],
    ['malformed', 'Malformed response'],
    ['loading', 'Loading'],
  ];
  for (const [state, label] of options) {
    const button = node('button', 'preview-button', label);
    button.type = 'button';
    button.addEventListener('click', () => showPreview(state));
    controls.append(button);
  }
  details.append(controls);
  container.append(details);
}

function previewResponse(status) {
  const abstained = status === 'abstained';
  return {
    schema_version: 'footballgpt-response-v1',
    request_id: 'preview-request',
    status,
    support_status: abstained ? 'unknown' : 'conditional',
    answer_mode: abstained ? 'abstain' : 'extractive_evidence_brief',
    answer: abstained
      ? 'Synthetic preview: no adequately supported passage was returned.'
      : 'Synthetic preview only. This sample illustrates where an API response appears; it is not tactical advice or a real source passage.',
    tactical_passages: abstained ? [] : [{
      evidence_id: 'fixture-only:sample',
      source_id: 'fixture-only',
      source_title: 'Synthetic UI fixture — not a UEFA document',
      page: 1,
      citation: 'Synthetic citation (preview only)',
      excerpt: 'Synthetic sample excerpt for layout preview only.',
      score: 0.5,
    }],
    event_evidence: abstained ? null : {
      evidence_id: 'fixture-only:event',
      match_id: 'synthetic-match',
      trigger_event_id: 'synthetic-event',
      trigger_event_type: 'Sample event',
      trigger_timestamp: '00:00:00.000',
      window_rule: 'Synthetic preview record',
      events: [{ type: 'Sample event', timestamp: '00:00:00.000', note: 'Synthetic preview data' }],
    },
    historical_examples: abstained ? [] : [{
      evidence_id: 'fixture-only:history',
      match_id: 'synthetic-match',
      team: 'Sample side',
      opponent: 'Sample opponent',
      timestamp: '00:00:00.000',
      event_type: 'Sample event',
      historical_score: 0.5,
      source_split: 'synthetic fixture',
      label: 'Synthetic UI fixture — not a historical match example',
    }],
    provenance: { schema_version: 'rgg-provenance-v1', question_id: 'preview-question', nodes: [{ id: 'fixture-only:sample', node_type: 'synthetic_preview' }], edges: [{ source: 'preview-question', target: 'fixture-only:sample', relation: 'preview_only' }] },
    limitations: ['Synthetic fixture data; not returned by the API.', 'Event data cannot establish off-ball movement or unseen video context.'],
  };
}

function showPreview(state) {
  requestStatus.textContent = 'Synthetic UI preview. No API request was sent.';
  if (state === 'service') {
    showError('Service temporarily unavailable', 'The service could not complete the request. Try again in a moment.', 'Preview only · synthetic HTTP 500 case.');
    return;
  }
  if (state === 'network') {
    showError('Could not reach the API', 'Check that the backend is running and the API base URL is correct, then try again.', 'Preview only · synthetic network failure.');
    return;
  }
  if (state === 'malformed') {
    showError('The response did not match the API contract', 'The response is incomplete or malformed. Try again; malformed content was not presented as evidence.', 'Preview only · synthetic malformed response.');
    return;
  }
  resultContent.replaceChildren();
  if (state === 'loading') {
    const loading = node('div', 'loading-state');
    append(loading, node('span', 'spinner', ''));
    append(loading, node('h3', '', 'Gathering the returned evidence'));
    append(loading, node('p', '', 'Synthetic loading preview; no request is in progress.'));
    resultContent.append(node('div', 'preview-banner', 'SYNTHETIC UI PREVIEW · Not an API response'));
    resultContent.append(loading);
    showBadge('Loading preview', 'loading');
    return;
  }
  renderResponse(previewResponse(state), { preview: true });
}

function safeApiUrl() {
  let base;
  try {
    base = new URL(apiInput.value.trim());
  } catch {
    return null;
  }
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password) return null;
  return `${base.origin}${base.pathname.replace(/\/+$/, '')}${API_PATH}`;
}

questionInput.addEventListener('input', () => {
  charCount.textContent = `${Array.from(questionInput.value).length.toLocaleString()} / 2,000`;
  const message = validationMessage(questionInput.value);
  questionError.textContent = message;
  questionInput.setAttribute('aria-invalid', message ? 'true' : 'false');
});

apiInput.addEventListener('change', () => {
  const value = apiInput.value.trim();
  if (value) localStorage.setItem(STORE_KEY, value);
  else localStorage.removeItem(STORE_KEY);
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  const invalidMessage = validationMessage(questionInput.value);
  questionError.textContent = invalidMessage;
  questionInput.setAttribute('aria-invalid', invalidMessage ? 'true' : 'false');
  if (invalidMessage) {
    questionInput.focus();
    showBadge('Check question', 'warning');
    requestStatus.textContent = invalidMessage;
    return;
  }

  const endpoint = safeApiUrl();
  if (!endpoint) {
    showError('Check the API address', 'Enter a valid HTTP or HTTPS API base URL, such as http://127.0.0.1:8000.');
    apiInput.focus();
    return;
  }

  const context = {};
  if (matchInput.value.trim()) context.match_id = matchInput.value.trim();
  if (triggerInput.value.trim()) context.trigger_event_id = triggerInput.value.trim();
  const body = { question };
  if (Object.keys(context).length) body.context = context;

  submitButton.disabled = true;
  submitButton.querySelector('.button-label').textContent = 'Reviewing…';
  results.setAttribute('aria-busy', 'true');
  resultContent.replaceChildren();
  const loading = node('div', 'loading-state');
  append(loading, node('span', 'spinner', ''));
  append(loading, node('h3', '', 'Gathering the returned evidence'));
  append(loading, node('p', '', 'Your question stays here while the API prepares a response.'));
  resultContent.append(loading);
  showBadge('Loading', 'loading');
  requestStatus.textContent = 'Request in progress.';

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });
    let payload;
    try {
      payload = await response.json();
    } catch {
      showError('The service returned an unreadable response', 'Try again. No response content was shown as evidence.');
      return;
    }

    if (!response.ok) {
      const apiMessage = payload?.schema_version === 'footballgpt-error-v1' && typeof payload?.error?.message === 'string'
        ? payload.error.message
        : '';
      const message = response.status >= 500
        ? 'The service could not complete the request. Try again in a moment.'
        : (apiMessage || 'The question could not be accepted. Review the request and try again.');
      showError(response.status >= 500 ? 'Service temporarily unavailable' : 'Request not accepted', message, `Request failed with HTTP ${response.status}.`);
      return;
    }

    if (!validateResponse(payload)) {
      showError('The response did not match the API contract', 'The response is incomplete or malformed. Try again; malformed content was not presented as evidence.');
      return;
    }
    renderResponse(payload);
  } catch (error) {
    const timedOut = error?.name === 'TimeoutError';
    showError(timedOut ? 'The request took too long' : 'Could not reach the API', timedOut
      ? 'The service did not respond within 30 seconds. Try again.'
      : 'Check that the backend is running and the API base URL is correct, then try again.', timedOut ? 'Request timed out.' : 'Network request failed.');
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector('.button-label').textContent = 'Review evidence';
    results.setAttribute('aria-busy', 'false');
  }
});

questionInput.setAttribute('aria-invalid', 'false');
makePreviewTools();
