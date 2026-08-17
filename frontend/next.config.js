const nextConfig = {
  turbopack: {
    root: __dirname,
  },
  // The toddler experience and the path-based levels routes are gone; the
  // curriculum is now class -> subject -> topic under /adventure. These are
  // temporary (307) rather than permanent so the old URLs are not cached
  // forever by anyone who bookmarked them during the prototype.
  redirects() {
    return [
      { source: '/toddler', destination: '/adventure', permanent: false },
      { source: '/toddler/:path*', destination: '/adventure', permanent: false },
      { source: '/levels', destination: '/adventure', permanent: false },
      { source: '/levels/:path*', destination: '/adventure', permanent: false },
    ];
  },
};

module.exports = nextConfig;
