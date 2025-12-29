const CACHE_NAME = 'Sistem-prezena-1';
const urlsToCache = [
  '/',
  '/static/manifest.json',
  '/register',
  '/reregister-device',
  '/student/scan',
  '/verify'
];

//Se instaleaza cacherele initiale
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
      .catch(err => {
        console.log('Cache failed:', err);
      })
  );
  self.skipWaiting();
});

// Se porneste curatarea cach-urilor vechi
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Se porneste gestionarea fetch-urilor
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Se gaseste in cache - returneaza raspunsul
        if (response) {
          return response;
        }

        //Clone la rquest
        const fetchRequest = event.request.clone();

        return fetch(fetchRequest).then(response => {
          // Se vede daca raspunsul este valid
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }

          // Se cach-eaza raspunsul
          const responseToCache = response.clone();

          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });

          return response;
        }).catch(error => {
          console.log('Fetch failed:', error);
          // AIci iti spune ca e offline  
          return new Response('Offline - vezi ca trebuie sa ai internet', {
            status: 503,
            statusText: 'Service nu este disponibil, posibil ca esti offline',
            headers: new Headers({
              'Content-Type': 'text/plain'
            })
          });
        });
      })
  );
});

// Mesaje pentru clienti
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
