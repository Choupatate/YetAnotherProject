(function () {
  var container = document.getElementById("FamilyChart");
  if (!container || !window.f3) return;

  var treeUrl = container.dataset.treeUrl;
  var fallbackAvatar = container.dataset.fallbackAvatar;

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value || "";
    return div.innerHTML;
  }

  function toGender(value) {
    if (value === "m") return "M";
    if (value === "f") return "F";
    return undefined; // never assume a gender when it isn't known
  }

  function toDatum(person) {
    return {
      id: person.id,
      data: {
        label: person.name,
        avatar: person.photo || fallbackAvatar,
        gender: toGender(person.gender),
      },
      rels: {
        parents: (person.rels && person.rels.parents) || [],
        spouses: (person.rels && person.rels.partners) || [],
        children: (person.rels && person.rels.children) || [],
      },
    };
  }

  fetch(treeUrl)
    .then(function (response) {
      return response.json();
    })
    .then(function (payload) {
      // Only people linked into the blood/partner graph become chart
      // cards; friends and fully unlinked people live in the plain HTML
      // "Friends & others" list rendered server-side below the chart.
      var familyPeople = payload.people.filter(function (p) {
        return !!p.rels;
      });
      if (!familyPeople.length) return;

      var urlById = {};
      familyPeople.forEach(function (p) {
        urlById[p.id] = p.url;
      });

      function cardInnerHtml(node) {
        var d = node.data.data;
        return (
          '<div class="card-inner">' +
          '<img class="f3-card-avatar" src="' + escapeHtml(d.avatar) + '" alt="">' +
          '<div class="f3-card-name">' + escapeHtml(d.label) + "</div>" +
          "</div>"
        );
      }

      function onCardClick(event, node) {
        // The library's default click behavior re-roots the tree; we keep
        // that on the mini-tree corner control only, and make the rest of
        // the card navigate to the person's page instead.
        if (event.target.closest(".mini-tree")) {
          chart.updateMainId(node.data.id);
          chart.updateTree({});
          return;
        }
        window.location.href = urlById[node.data.id];
      }

      var chart = window.f3
        .createChart("#FamilyChart", familyPeople.map(toDatum))
        .setTransitionTime(600)
        .setOrientationVertical()
        .setSingleParentEmptyCard(false);

      chart
        .setCardHtml()
        .setMiniTree(true)
        .setCardInnerHtmlCreator(cardInnerHtml)
        .setOnCardClick(onCardClick);

      if (payload.anchor && urlById.hasOwnProperty(payload.anchor)) {
        chart.updateMainId(payload.anchor);
      }

      chart.updateTree({ initial: true });
    })
    .catch(function () {
      container.textContent = "Could not load the family tree.";
    });
})();
