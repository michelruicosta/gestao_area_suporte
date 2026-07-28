/**
 * Cálculo único de Pendente/Aguardando/Concluído/Não resolvidos, usado pela
 * tela de Triagem (email_operacional.html) e pela tela inicial (index.html).
 * As duas telas carregam este mesmo arquivo — nunca duplicar esta lógica.
 *
 * Extraído em 01/07/2026 de email_operacional.html sem mudar nenhum comportamento
 * (ver documentações/REVISAO_TELAS.md, pendência 1, e REGISTRO_CORRECOES.md).
 */

function parseDate(dateStr){
  if(!dateStr) return null;
  var parts = dateStr.split('/');
  if(parts.length === 3)
    return new Date(parseInt(parts[2],10), parseInt(parts[1],10)-1, parseInt(parts[0],10));
  parts = dateStr.split('-');
  if(parts.length === 3)
    return new Date(parseInt(parts[0],10), parseInt(parts[1],10)-1, parseInt(parts[2],10));
  return null;
}

function parseDateTime(dateStr, timeStr){
  if(!dateStr || !timeStr) return null;
  var date = parseDate(dateStr);
  if(!date) return null;
  var timePart = (timeStr + '').trim();
  if (timePart.indexOf(' ') !== -1) timePart = timePart.split(/\s+/).pop();
  var colon = timePart.indexOf(':');
  if (colon === -1) return date;
  var h = parseInt(timePart.substring(0, colon), 10);
  var m = parseInt(timePart.substring(colon + 1), 10);
  if (Number.isNaN(h)) h = 0;
  if (Number.isNaN(m)) m = 0;
  date.setHours(h, m, 0, 0);
  return date;
}

// ===== THREAD GROUPING =====
function groupByThread(data){
  const threads = {};
  data.forEach(item => {
    const tid = item.threadId || item.id;
    if(!threads[tid]){
      threads[tid] = [];
    }
    threads[tid].push(item);
  });

  // Ordena emails dentro de cada thread por timestamp
  Object.keys(threads).forEach(tid => {
    threads[tid].sort((a, b) => {
      const dateA = parseDateTime(a.data_iso, a.timestamp);
      const dateB = parseDateTime(b.data_iso, b.timestamp);
      return dateA - dateB;
    });
  });

  return threads;
}

function getThreadLatest(threadEmails){
  // Retorna o último email da thread (mais recente)
  return threadEmails[threadEmails.length - 1];
}

/** threadId âncora do card fundido: assunto mais longo; empate → ordem lexicográfica.
 * Lê THREADS do escopo global da página (compartilhado entre scripts clássicos). */
function canonicalParTidForMerge(tidA, tidB) {
  var a = String(tidA), b = String(tidB);
  var rowsA = THREADS[a] || [];
  var rowsB = THREADS[b] || [];
  var la = rowsA.length ? getThreadLatest(rowsA) : null;
  var lb = rowsB.length ? getThreadLatest(rowsB) : null;
  var lenA = (la && (la.titulo || la.assunto)) ? String(la.titulo || la.assunto).length : 0;
  var lenB = (lb && (lb.titulo || lb.assunto)) ? String(lb.titulo || lb.assunto).length : 0;
  if (lenB !== lenA) return lenB > lenA ? b : a;
  return a < b ? a : b;
}

/** Par sugerido recíproco (PAR_SUGERIDOS bidirecional) ou par confirmado bidirecional.
 * Lê PAR_SUGERIDOS/PAR_CONFIRMADOS do escopo global da página. */
function getReciprocalParPeer(tid) {
  var t = String(tid || "").trim();
  if (!t) return null;
  var sug = PAR_SUGERIDOS[t];
  if (sug && sug.length === 1 && sug[0] && sug[0].threadId) {
    var ot = String(sug[0].threadId).trim();
    var sugO = PAR_SUGERIDOS[ot];
    if (sugO && sugO.length === 1 && sugO[0] && String(sugO[0].threadId).trim() === t) return ot;
  }
  var c = PAR_CONFIRMADOS[t];
  if (c && String(PAR_CONFIRMADOS[c] || "").trim() === t) return String(c).trim();
  return null;
}

/** Mesma regra que _evento_concluido_operacional no painel (Fog CLOSED, CONCLUÍDO, etc.). */
function eventoConcluidoOperacional(ev){
  if (!ev) return false;
  var st = String(ev.status || '').trim().toLowerCase();
  if (st === 'concluido' || st === 'closed' || st === 'resolved' || st === 'fechado') return true;
  var sp = String(ev.status_processo || '').trim().toUpperCase().replace('Í', 'I');
  if (sp === 'CONCLUIDO' || sp === 'CLOSED' || sp === 'RESOLVED' || sp === 'FECHADO') return true;
  return false;
}

/**
 * KPIs operacional: um "latest" por caso lógico — par recíproco (PAR_SUGERIDOS / PAR_CONFIRMADOS)
 * com ambos os threadId no mesmo mapa conta **1** vez (Pendentes, Concluídos na data, Aguardando, Não resolvidos).
 */
function latestPorCasoOperacionalDedupPar(threadsMap) {
  if (!threadsMap || typeof threadsMap !== "object") return [];
  var tids = Object.keys(threadsMap);
  var consumed = new Set();
  var out = [];
  tids.forEach(function(tid) {
    if (consumed.has(tid)) return;
    var peer = getReciprocalParPeer(tid);
    if (peer && threadsMap[peer] !== undefined) {
      consumed.add(tid);
      consumed.add(peer);
      var can = canonicalParTidForMerge(tid, peer);
      var rows = threadsMap[can] || threadsMap[tid];
      if (rows && rows.length) out.push(getThreadLatest(rows));
    } else {
      consumed.add(tid);
      var r = threadsMap[tid];
      if (r && r.length) out.push(getThreadLatest(r));
    }
  });
  return out;
}

/**
 * Monta os buckets Abertos/Concluídos/Aguardando/Não resolvidos + Abertos-sem-Aguardando
 * para um dia, a partir do mesmo payload que a Triagem usa (/api/dados). Sem filtros de
 * usuário (responsável/empresa/categoria/busca) — é a base que as duas telas compartilham.
 * Cada tela decide o que fazer com os mapas retornados (Triagem continua filtrando/ordenando
 * para a lista; a Home só usa o tamanho de cada bucket, já deduplicado por par/cluster).
 *
 * threads: THREADS já montado (groupByThread) para o dia de referência.
 * aguardandoIds / naoResolvidosIds: Set<threadId> (payload.aguardando / payload.nao_resolvidos).
 */
function montarBucketsKpisEmailDia(threads, aguardandoIds, naoResolvidosIds) {
  const threadsAbertos = {};
  const threadsConcluidos = {};
  Object.keys(threads).forEach(tid => {
    const latest = getThreadLatest(threads[tid]);
    if (eventoConcluidoOperacional(latest)) threadsConcluidos[tid] = threads[tid];
    else threadsAbertos[tid] = threads[tid];
  });

  const threadsAbertosPendentes = {};
  Object.keys(threadsAbertos).forEach(tid => {
    if (!aguardandoIds.has(tid)) threadsAbertosPendentes[tid] = threadsAbertos[tid];
  });

  const threadsAguardando = {};
  aguardandoIds.forEach(function(tid){
    if (!threads[tid]) return;
    if (naoResolvidosIds.has(tid)) return;
    const latest = getThreadLatest(threads[tid]);
    if (eventoConcluidoOperacional(latest)) return;
    threadsAguardando[tid] = threads[tid];
  });

  const threadsNaoResolvidos = {};
  naoResolvidosIds.forEach(function(tid){
    if (!threads[tid]) return;
    const latest = getThreadLatest(threads[tid]);
    if (eventoConcluidoOperacional(latest)) return;
    threadsNaoResolvidos[tid] = threads[tid];
  });

  return { threadsAbertos, threadsConcluidos, threadsAguardando, threadsNaoResolvidos, threadsAbertosPendentes };
}

/** Conveniência para a Home: já devolve os 4 números finais (deduplicados por par/cluster). */
function calcularContagemKpisEmailDia(threads, aguardandoIds, naoResolvidosIds) {
  const b = montarBucketsKpisEmailDia(threads, aguardandoIds, naoResolvidosIds);
  return {
    pendente: latestPorCasoOperacionalDedupPar(b.threadsAbertosPendentes).length,
    aguardando: latestPorCasoOperacionalDedupPar(b.threadsAguardando).length,
    concluido: latestPorCasoOperacionalDedupPar(b.threadsConcluidos).length,
    naoResolvidos: latestPorCasoOperacionalDedupPar(b.threadsNaoResolvidos).length,
  };
}
