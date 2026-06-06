import os, re

base = r'C:\auto_output\bnbbaijkgj\h5-web\src\app'
prefix = 'src/app'
routes = []

for root, dirs, files in os.walk(base):
    for f in files:
        if f == 'page.tsx':
            full = os.path.join(root, f)
            rel = os.path.relpath(full, base).replace('\\', '/')
            if rel.startswith('_archived_tabs'):
                continue
            route = re.sub(r'^\(ai-chat\)/', '', rel)
            route = re.sub(r'/page\.tsx$', '', route)
            if route == 'page.tsx':
                route = '/'
            else:
                route = '/' + route
            depth = route.count('/')
            routes.append((depth, route, rel))

routes.sort(key=lambda x: (x[0], x[1]))

for depth, route, rel in routes:
    print('[H5] %s \u2190 h5-web/%s/%s:1' % (route, prefix, rel))
print('')
print('Total H5 routes: %d' % len(routes))
