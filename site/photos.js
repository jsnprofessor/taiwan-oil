// Station photos from Google Places. Each image counts toward the daily free quota,
// so only the photo on screen is requested. Google allows no caching of photos or
// their URLs, so the list is fetched fresh every time a card opens (that request is free).

const PHOTO_WIDTH = 800;
let Place = null;

async function placePhotos(pid) {
  Place ??= (await google.maps.importLibrary("places")).Place;
  const place = new Place({ id: pid });
  await place.fetchFields({ fields: ["photos"] }); // id + photos only: the free tier
  return place.photos ?? [];
}

function node(tag, className, ...children) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  n.append(...children);
  return n;
}

function link(href, text) {
  const a = node("a", "", text);
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener";
  return a;
}

function message(text) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#i-pump");
  svg.append(use);
  return node("div", "st-photo-msg", svg, node("span", "", text));
}

function slide(photo) {
  const img = node("img", "");
  img.alt = "";
  img.decoding = "async";
  const fig = node("figure", "st-photo", img);
  const author = photo.authorAttributions?.[0];
  if (author) {
    fig.append(node("figcaption", "st-photo-author", "相片：",
      author.uri ? link(author.uri, author.displayName) : author.displayName));
  }
  img.addEventListener("error", () => fig.replaceChildren(message("相片暫時無法顯示")), { once: true });
  const load = () => { if (!img.getAttribute("src")) img.src = photo.getURI({ maxWidth: PHOTO_WIDTH }); };
  return { fig, load };
}

async function fill(box, pid) {
  let photos = null;
  try {
    photos = await placePhotos(pid);
  } catch {
    // network or quota: shown below
  }
  if (!box.isConnected) return; // another station's card has replaced this one
  if (photos === null) return box.replaceChildren(message("相片暫時無法顯示"));
  if (photos.length === 0) return box.replaceChildren(message("暫無相片"));

  const slides = photos.map(slide);
  const strip = node("div", "st-photo-strip", ...slides.map((s) => s.fig));
  const count = node("div", "st-photo-count");
  const observer = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const i = slides.findIndex((s) => s.fig === e.target);
      slides[i].load();
      count.textContent = slides.length > 1 ? `${i + 1} / ${slides.length}` : "";
    }
  }, { root: strip, threshold: 0.6 });
  slides.forEach((s) => observer.observe(s.fig));
  box.replaceChildren(strip, count);
}

// Reserves a 16:9 area straight away so the card doesn't jump when photos arrive.
export function photoSection(pid) {
  const box = node("div", "st-photos");
  box.setAttribute("aria-label", "加油站相片");
  fill(box, pid);
  const listing = `https://www.google.com/maps/place/?q=place_id:${encodeURIComponent(pid)}`;
  return node("div", "st-photo-block", box,
    node("div", "st-photo-credit", node("span", "", "Google Maps"), link(listing, "在 Google 地圖查看更多相片")));
}
