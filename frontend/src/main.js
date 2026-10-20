import './styles.css';

const API_PATH = '/api/v1/ask';
const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const UEFA_REPORTS_URL = 'https://www.uefa.com/news-media/publications/technical-reports/';
const STORE_KEY = 'footballgpt-api-base-url';
let provenanceGraphId = 0;

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
  // A malformed provenance trace should not hide an otherwise valid answer.
  if (payload.status === 'abstained' && (payload.answer_mode !== 'abstain' || payload.tactical_passages.length !== 0)) return false;
  if (payload.status === 'answered' && payload.answer_mode !== 'extractive_evidence_brief') return false;
  if (!payload.tactical_passages.every((item) => isRecord(item) && requiredString(item.evidence_id) && requiredString(item.source_id) && requiredString(item.source_title) && Number.isInteger(item.page) && requiredString(item.citation) && requiredString(item.excerpt) && typeof item.score === 'number' && Number.isFinite(item.score))) return false;
  if (!payload.historical_examples.every((item) => isRecord(item) && requiredString(item.evidence_id) && requiredString(item.match_id) && requiredString(item.source_split) && requiredString(item.label) && typeof item.historical_score === 'number' && Number.isFinite(item.historical_score))) return false;
  if (!payload.limitations.every((item) => typeof item === 'string')) return false;
  if (payload.event_evidence && (!Array.isArray(payload.event_evidence.events) || !requiredString(payload.event_evidence.evidence_id) || !requiredString(payload.event_evidence.match_id) || !requiredString(payload.event_evidence.trigger_event_id) || !requiredString(payload.event_evidence.trigger_event_type) || !requiredString(payload.event_evidence.trigger_timestamp) || !requiredString(payload.event_evidence.window_rule) || !payload.event_evidence.events.every(isRecord))) return false;
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

  for (const [index, passage] of passages.entries()) {
    const card = node('article', 'passage-card');
    card.id = `passage-card-${index}`;
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

function humanize(value) {
  if (typeof value !== 'string' || !value.trim()) return 'Not provided';
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortText(value, max = 86) {
  if (typeof value !== 'string') return '';
  const compact = value.replace(/\s+/g, ' ').trim();
  return compact.length > max ? `${compact.slice(0, max - 1)}…` : compact;
}

function nodeType(nodeData) {
  return typeof nodeData.node_type === 'string' && nodeData.node_type.trim()
    ? nodeData.node_type
    : 'unknown';
}

function nodeLabel(nodeData) {
  const type = nodeType(nodeData);
  const id = typeof nodeData.id === 'string' ? nodeData.id : '';
  if (type === 'question') return nodeData.text || nodeData.label || id || 'Question';
  if (type === 'uefa_text_chunk') {
    const source = nodeData.source_title || nodeData.source_id || nodeData.citation || 'UEFA text chunk';
    const page = nodeData.page !== undefined && nodeData.page !== null ? ` · page ${nodeData.page}` : '';
    return `${source}${page}`;
  }
  if (type === 'statsbomb_event_window') {
    const event = nodeData.trigger_event_type || nodeData.event_type || 'Recorded event window';
    const time = nodeData.trigger_timestamp || nodeData.timestamp;
    return [event, time, nodeData.match_id ? `Match ${nodeData.match_id}` : null].filter(Boolean).join(' · ');
  }
  if (type === 'historical_situation') {
    const match = nodeData.match_id ? `Match ${nodeData.match_id}` : null;
    const matchup = [nodeData.team, nodeData.opponent].filter(Boolean).join(' vs ');
    return [nodeData.event_type, matchup, match].filter(Boolean).join(' · ') || nodeData.label || id || 'Historical situation';
  }
  return nodeData.label || nodeData.title || nodeData.name || nodeData.text || id || 'Node';
}

function svgElement(tag, attrs = {}) {
  const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, String(value));
  return element;
}

function setSvgText(parent, x, y, text, className = '') {
  const label = svgElement('text', { x, y, class: className });
  label.textContent = text;
  parent.append(label);
  return label;
}

function renderGraphSvg(nodes, edges, passageTargets, mobile) {
  const width = mobile ? 360 : 720;
  const rowGap = mobile ? 88 : 102;
  const positions = new Map();
  let leftIndex = 0;
  let rightIndex = 0;
  const colWidth = mobile ? 300 : 286;
  const svg = svgElement('svg', {
    class: `provenance-svg ${mobile ? 'provenance-svg-mobile' : 'provenance-svg-desktop'}`,
    viewBox: `0 0 ${width} 145`,
    role: 'group',
    'aria-label': `${nodes.length} provenance nodes and ${edges.length} returned relationships. The complete textual map follows.`,
  });
  const defs = svgElement('defs');
  const marker = svgElement('marker', { id: `provenance-arrow-${++provenanceGraphId}`, viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse' });
  marker.append(svgElement('path', { d: 'M 0 0 L 10 5 L 0 10 z', class: 'provenance-arrowhead' }));
  defs.append(marker);
  svg.append(defs);

  const uniqueIndexes = new Map();
  nodes.forEach((item, index) => {
    if (typeof item.id !== 'string') return;
    uniqueIndexes.set(item.id, uniqueIndexes.has(item.id) ? null : index);
  });
  const layout = nodes.map((item, index) => {
    const type = nodeType(item);
    if (mobile) {
      const position = { x: 42, y: 28 + index * rowGap, width: colWidth, height: 58, centerX: 192, centerY: 57 + index * rowGap };
      positions.set(index, position);
      return position;
    }
    const left = type === 'question';
    const row = left ? leftIndex++ : rightIndex++;
    const position = { x: left ? 20 : 414, y: 25 + row * rowGap, width: colWidth, height: 70, centerX: (left ? 20 : 414) + colWidth / 2, centerY: 60 + row * rowGap };
    positions.set(index, position);
    return position;
  });
  const contentHeight = mobile ? nodes.length * rowGap + 15 : Math.max(leftIndex, rightIndex, 1) * rowGap + 10;
  svg.setAttribute('viewBox', `0 0 ${width} ${contentHeight}`);

  const markerId = marker.getAttribute('id');
  const edgesGroup = svgElement('g', { class: 'provenance-svg-edges', 'aria-hidden': 'true' });
  for (const edge of edges) {
    if (typeof edge.source !== 'string' || typeof edge.target !== 'string') continue;
    const sourceIndex = uniqueIndexes.get(edge.source);
    const targetIndex = uniqueIndexes.get(edge.target);
    if (sourceIndex === undefined || sourceIndex === null || targetIndex === undefined || targetIndex === null) continue;
    const source = layout[sourceIndex];
    const target = layout[targetIndex];
    if (!source || !target) continue;
    if (mobile) {
      const lane = 18 + (edges.indexOf(edge) % 5) * 4;
      edgesGroup.append(svgElement('path', { d: `M 42 ${source.centerY} H ${lane} V ${target.centerY} H 42`, class: 'provenance-edge-line', 'marker-end': `url(#${markerId})` }));
    } else {
      const fromLeft = source.x < width / 2;
      const sx = fromLeft ? source.x + source.width : source.x;
      const tx = target.x < width / 2 ? target.x + target.width : target.x;
      const curve = (sx + tx) / 2;
      edgesGroup.append(svgElement('path', { d: `M ${sx} ${source.centerY} C ${curve} ${source.centerY}, ${curve} ${target.centerY}, ${tx} ${target.centerY}`, class: 'provenance-edge-line', 'marker-end': `url(#${markerId})` }));
    }
  }
  svg.append(edgesGroup);

  nodes.forEach((item, index) => {
    const position = layout[index];
    const type = nodeType(item);
    const label = shortText(String(nodeLabel(item)), mobile ? 42 : 39);
    const identity = typeof item.id === 'string' ? ` · ${item.id}` : '';
    const accessibleName = `${humanize(type)}: ${nodeLabel(item)}${identity}`;
    const passageIndex = typeof item.evidence_id === 'string' ? passageTargets.get(item.evidence_id) : undefined;
    const wrapper = passageIndex !== undefined
      ? svgElement('a', { href: `#passage-card-${passageIndex}`, class: 'provenance-svg-node-link', 'aria-label': `${accessibleName}. Jump to matching source passage.` })
      : svgElement('g', { class: 'provenance-svg-node', tabindex: '0', role: 'group', 'aria-label': accessibleName });
    wrapper.classList.add(`type-${type.replace(/[^a-z0-9_-]/gi, '-')}`);
    wrapper.append(svgElement('rect', { x: position.x, y: position.y, width: position.width, height: position.height, rx: type === 'question' ? 17 : 5, class: 'provenance-node-card' }));
    const badgeX = position.x + 18;
    const badgeY = position.centerY;
    if (type === 'historical_situation') {
      wrapper.append(svgElement('path', { d: `M ${badgeX} ${badgeY - 9} l 9 9 l -9 9 l -9 -9 z`, class: 'provenance-node-symbol' }));
    } else if (type === 'statsbomb_event_window') {
      wrapper.append(svgElement('circle', { cx: badgeX, cy: badgeY, r: 8, class: 'provenance-node-symbol' }));
    } else {
      wrapper.append(svgElement('rect', { x: badgeX - 8, y: badgeY - 8, width: 16, height: 16, rx: type === 'question' ? 5 : 1, class: 'provenance-node-symbol' }));
    }
    setSvgText(wrapper, position.x + 34, position.y + (mobile ? 24 : 28), label, 'provenance-node-label');
    setSvgText(wrapper, position.x + 34, position.y + (mobile ? 42 : 49), shortText(identity.trim() || humanize(type), 36), 'provenance-node-id');
    svg.append(wrapper);
  });
  return svg;
}

function renderProvenance(provenance, response) {
  const block = section('Evidence provenance', 'RETURNED FOR THIS RESPONSE', 'provenance-section');
  append(block, node('p', 'provenance-explainer', 'This view shows evidence and context returned for this response, not every retrieval candidate or the full internal retrieval graph. Links describe recorded relationships; they do not prove causality, tactical effectiveness, or coach approval.'));
  if (provenance === null || provenance === undefined) {
    append(block, node('p', 'section-empty', 'Provenance was not returned for this response. Check the limitations below for the API explanation.'));
    return block;
  }
  if (typeof provenance !== 'object' || Array.isArray(provenance)) {
    append(block, node('p', 'section-empty', 'The API returned malformed provenance data; no graph was drawn. The answer and other valid evidence remain available.'));
    append(block, node('pre', 'json-block', formatValue(provenance)));
    return block;
  }
  if (provenance.schema_version && provenance.schema_version !== 'rgg-provenance-v1') {
    append(block, node('p', 'provenance-warning', 'The provenance schema version is unrecognized. Returned node and relationship entries are shown only where their shapes are valid.'));
  }
  const rawNodes = provenance.nodes;
  const rawEdges = provenance.edges;
  if (!Array.isArray(rawNodes) || !Array.isArray(rawEdges)) {
    append(block, node('p', 'section-empty', 'Provenance graph data is incomplete or malformed; nodes and edges must be returned as lists. No graph was drawn.'));
  }
  const nodes = Array.isArray(rawNodes) ? rawNodes.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) : [];
  const edges = Array.isArray(rawEdges) ? rawEdges.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) : [];
  const invalidNodeCount = Array.isArray(rawNodes) ? rawNodes.length - nodes.length : 0;
  const invalidEdgeCount = Array.isArray(rawEdges) ? rawEdges.length - edges.length : 0;
  const summary = node('div', 'provenance-counts');
  append(summary, node('span', '', `${nodes.length} node${nodes.length === 1 ? '' : 's'}`));
  append(summary, node('span', '', `${edges.length} relationship${edges.length === 1 ? '' : 's'}`));
  append(block, summary);
  if (invalidNodeCount || invalidEdgeCount) {
    append(block, node('p', 'provenance-warning', `${invalidNodeCount} malformed node entr${invalidNodeCount === 1 ? 'y' : 'ies'} and ${invalidEdgeCount} malformed relationship entr${invalidEdgeCount === 1 ? 'y' : 'ies'} were omitted. Every valid returned node and relationship is listed below.`));
  }

  if (!nodes.length && !edges.length && Array.isArray(rawNodes) && Array.isArray(rawEdges)) {
    append(block, node('p', 'section-empty', 'No provenance nodes or relationships were returned for this response.'));
  } else if (nodes.length || edges.length) {
    const passageTargets = new Map();
    const passageMatches = new Map();
    response.tactical_passages.forEach((passage, index) => {
      passageMatches.set(passage.evidence_id, (passageMatches.get(passage.evidence_id) || 0) + 1);
      passageTargets.set(passage.evidence_id, index);
    });
    for (const item of nodes) {
      if (typeof item.evidence_id === 'string' && passageMatches.get(item.evidence_id) !== 1) passageTargets.delete(item.evidence_id);
    }
    // Only evidence IDs that resolve to exactly one passage are linkable.
    for (const item of nodes) {
      if (typeof item.evidence_id === 'string' && passageMatches.get(item.evidence_id) === 1) continue;
      if (typeof item.evidence_id === 'string') passageTargets.delete(item.evidence_id);
    }
    append(block, renderGraphSvg(nodes, edges, passageTargets, false));
    append(block, renderGraphSvg(nodes, edges, passageTargets, true));

    const legend = node('div', 'provenance-legend');
    append(legend, node('strong', '', 'Node key'));
    const legendTypes = [
      ['question', 'Question'], ['uefa_text_chunk', 'UEFA passage'],
      ['statsbomb_event_window', 'Recorded event window'], ['historical_situation', 'Historical situation'],
    ];
    for (const [type, label] of legendTypes) {
      if (!nodes.some((item) => nodeType(item) === type)) continue;
      const item = node('span', `legend-item type-${type}`, label);
      item.prepend(node('span', 'legend-shape', ''));
      legend.append(item);
    }
    const unknownTypes = [...new Set(nodes.map(nodeType).filter((type) => !legendTypes.some(([known]) => known === type)))];
    if (unknownTypes.length) append(legend, node('span', 'legend-item', `Other: ${unknownTypes.map(humanize).join(', ')}`));
    block.append(legend);

    const nodeHeading = node('h4', 'provenance-subheading', 'Nodes');
    append(block, nodeHeading);
    const connectedIds = new Set();
    for (const edge of edges) {
      if (typeof edge.source === 'string') connectedIds.add(edge.source);
      if (typeof edge.target === 'string') connectedIds.add(edge.target);
    }
    const nodeList = node('ul', 'provenance-list provenance-node-list');
    for (const [index, item] of nodes.entries()) {
      const li = node('li', `provenance-node-item${typeof item.id !== 'string' || !connectedIds.has(item.id) ? ' is-disconnected' : ''}`);
      append(li, node('span', 'node-type', humanize(nodeType(item))));
      const copy = node('div', 'provenance-node-copy');
      append(copy, node('span', 'provenance-node-title', nodeLabel(item)));
      append(copy, node('span', 'node-id', typeof item.id === 'string' ? item.id : 'Identifier not provided'));
      const fields = Object.entries(item).filter(([key]) => !['id', 'node_type'].includes(key));
      if (fields.length) {
        const details = document.createElement('details');
        details.className = 'provenance-node-details';
        const summaryLine = document.createElement('summary');
        summaryLine.textContent = 'Returned node fields';
        details.append(summaryLine);
        const fieldList = node('dl', 'provenance-field-list');
        for (const [key, value] of fields) {
          fieldList.append(node('dt', '', humanize(key)));
          fieldList.append(node('dd', '', formatValue(value)));
        }
        details.append(fieldList);
        copy.append(details);
      }
      const passageIndex = typeof item.evidence_id === 'string' && passageTargets.has(item.evidence_id) ? passageTargets.get(item.evidence_id) : undefined;
      if (passageIndex !== undefined) {
        const link = node('a', 'provenance-passage-link', 'Jump to matching source passage');
        link.href = `#passage-card-${passageIndex}`;
        copy.append(link);
      }
      li.append(copy);
      nodeList.append(li);
    }
    block.append(nodeList);

    append(block, node('h4', 'provenance-subheading', 'Relationships'));
    if (edges.length) {
      const edgeList = node('ul', 'provenance-list edge-list');
      for (const edge of edges) {
        const li = node('li', 'provenance-edge-item');
        append(li, node('span', 'node-type', humanize(edge.relation)));
        const endpoints = node('span', 'node-id');
        const source = typeof edge.source === 'string' ? edge.source : 'Source not provided';
        const target = typeof edge.target === 'string' ? edge.target : 'Target not provided';
        endpoints.textContent = `${source} → ${target}`;
        if (typeof edge.source !== 'string' || typeof edge.target !== 'string') endpoints.textContent += ' · endpoint missing';
        li.append(endpoints);
        const relationFields = Object.entries(edge).filter(([key]) => !['source', 'target', 'relation'].includes(key));
        if (relationFields.length) {
          const extras = relationFields.map(([key, value]) => `${humanize(key)}: ${formatValue(value)}`).join(' · ');
          append(li, node('span', 'provenance-edge-extra', extras));
        }
        if (typeof edge.source === 'string' && typeof edge.target === 'string') {
          const endpointCount = (id) => nodes.filter((item) => item.id === id).length;
          if (endpointCount(edge.source) !== 1 || endpointCount(edge.target) !== 1) {
            append(li, node('span', 'provenance-edge-extra', 'One or both endpoints are missing or ambiguous among the returned nodes.'));
          }
        }
        edgeList.append(li);
      }
      block.append(edgeList);
    } else {
      append(block, node('p', 'section-empty', 'No relationships were returned; the listed nodes are shown without inferred links.'));
    }
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
  resultContent.append(renderProvenance(response.provenance, response));
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
    ['graph-empty', 'Empty provenance'],
    ['graph-missing', 'Missing provenance'],
    ['graph-malformed', 'Malformed provenance'],
    ['graph-disconnected', 'Disconnected node'],
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

function previewResponse(status, graphState = 'connected') {
  const abstained = status === 'abstained';
  const graphNodes = [
    { id: 'preview-question', node_type: 'question', text: 'Synthetic preview question: what evidence was returned?' },
    { id: 'fixture-only:sample', node_type: 'uefa_text_chunk', evidence_id: 'fixture-only:sample', citation: 'Synthetic citation (preview only)', source_id: 'fixture-only', page: 1 },
    { id: 'fixture-only:event', node_type: 'statsbomb_event_window', match_id: 'synthetic-match', trigger_event_type: 'Sample event', trigger_timestamp: '00:00:00.000' },
    { id: 'fixture-only:history', node_type: 'historical_situation', match_id: 'synthetic-match', team: 'Sample side', opponent: 'Sample opponent', event_type: 'Sample event' },
  ];
  const graphEdges = [
    { source: 'preview-question', target: 'fixture-only:sample', relation: 'retrieved_support', rank: 1 },
    { source: 'preview-question', target: 'fixture-only:event', relation: 'recorded_match_context' },
    { source: 'preview-question', target: 'fixture-only:history', relation: 'historical_similarity' },
  ];
  let provenance = { schema_version: 'rgg-provenance-v1', question_id: 'preview-question', nodes: graphNodes, edges: graphEdges };
  if (graphState === 'empty') provenance = { schema_version: 'rgg-provenance-v1', nodes: [], edges: [] };
  if (graphState === 'missing') provenance = null;
  if (graphState === 'malformed') provenance = { schema_version: 'rgg-provenance-v1', nodes: [graphNodes[0], null], edges: 'synthetic malformed edge list' };
  if (graphState === 'disconnected') provenance.nodes = [...graphNodes, { id: 'fixture-only:isolated', node_type: 'preview_unknown_type', label: 'Synthetic disconnected node' }];
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
    provenance,
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
  const graphState = state.startsWith('graph-') ? state.slice('graph-'.length) : 'connected';
  const responseState = state === 'abstained' ? 'abstained' : 'answered';
  renderResponse(previewResponse(responseState, graphState), { preview: true });
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
