/**
 * Folder search component — Phase D-post
 *
 * Debounced search against cached manifest. Results appear in a dropdown.
 * Clicking a result expands the tree to that folder via FolderTree.expandToFolder().
 */
(function () {
  'use strict';

  var input = document.getElementById('folder-search');
  var resultsEl = document.getElementById('search-results');
  if (!input || !resultsEl) return;

  var debounceTimer = null;
  var DEBOUNCE_MS = 300;

  input.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    var q = input.value.trim();
    if (q.length < 2) {
      hideResults();
      return;
    }
    debounceTimer = setTimeout(function () {
      doSearch(q);
    }, DEBOUNCE_MS);
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      hideResults();
      input.blur();
    }
  });

  // Close on outside click
  document.addEventListener('click', function (e) {
    if (!input.contains(e.target) && !resultsEl.contains(e.target)) {
      hideResults();
    }
  });

  function doSearch(query) {
    fetch('/admin/api/folders/search?q=' + encodeURIComponent(query))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderResults(data.results || [], data.total || 0, data.showing || 0, query);
      })
      .catch(function () {
        hideResults();
      });
  }

  function renderResults(results, total, showing, query) {
    resultsEl.innerHTML = '';

    if (results.length === 0) {
      var empty = document.createElement('div');
      empty.className = 'search-result-item';
      empty.style.color = 'var(--gray)';
      empty.textContent = 'No folders found';
      resultsEl.appendChild(empty);
      showResults();
      return;
    }

    for (var i = 0; i < results.length; i++) {
      var item = results[i];
      var el = document.createElement('div');
      el.className = 'search-result-item';

      var driveSpan = document.createElement('span');
      driveSpan.className = 'search-result-drive';
      driveSpan.textContent = item.drive_slug;
      el.appendChild(driveSpan);

      var pathSpan = document.createElement('span');
      pathSpan.className = 'search-result-path';
      pathSpan.innerHTML = highlightMatch(item.path, query);
      el.appendChild(pathSpan);

      // Click handler
      (function (driveSlug, folderId) {
        el.addEventListener('click', function () {
          hideResults();
          input.value = '';
          if (window.FolderTree && window.FolderTree.expandToFolder) {
            window.FolderTree.expandToFolder(driveSlug, folderId);
          }
        });
      })(item.drive_slug, item.folder_id);

      resultsEl.appendChild(el);
    }

    // "N more..." indicator
    if (total > showing) {
      var more = document.createElement('div');
      more.className = 'search-more';
      more.textContent = (total - showing) + ' more result' + (total - showing !== 1 ? 's' : '') + '...';
      resultsEl.appendChild(more);
    }

    showResults();
  }

  function highlightMatch(text, query) {
    var idx = text.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return escapeHtml(text);
    var before = text.substring(0, idx);
    var match = text.substring(idx, idx + query.length);
    var after = text.substring(idx + query.length);
    return escapeHtml(before) + '<mark>' + escapeHtml(match) + '</mark>' + escapeHtml(after);
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function showResults() {
    resultsEl.classList.remove('hidden');
  }

  function hideResults() {
    resultsEl.classList.add('hidden');
  }

})();
