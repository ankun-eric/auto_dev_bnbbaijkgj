import os, re

base = r'C:\auto_output\bnbbaijkgj\admin-web\src\app'
prefix = 'src/app'
routes = []

for root, dirs, files in os.walk(base):
    for f in files:
        if f == 'page.tsx':
            full = os.path.join(root, f)
            rel = os.path.relpath(full, base).replace('\\', '/')
            route = re.sub(r'^\(admin\)/', '', rel)
            route = re.sub(r'/page\.tsx$', '', route)
            if route == 'page.tsx':
                route = '/'
            else:
                route = '/' + route
            depth = route.count('/')
            routes.append((depth, route, rel))

routes.sort(key=lambda x: (x[0], x[1]))

for depth, route, rel in routes:
    print('[Admin] %s \u2190 admin-web/%s/%s:1' % (route, prefix, rel))
print('')
print('Total Admin routes: %d' % len(routes))
