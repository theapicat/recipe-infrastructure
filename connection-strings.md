## Connection string for utviklermiljø:

**Auth db**
```text
Host=localhost;Port=5432;Database=recipe_auth_db;Username=auth_user;Password=auth_secure_password_dev;Client Encoding=UTF8;
```

**Core db**
```text
Host=localhost;Port=5433;Database=recipe_core_db;Username=core_user;Password=core_secure_password_dev;Client Encoding=UTF8;
```

**Scraper db**
```text
Host=localhost;Port=5433;Database=recipe_core_db;Username=core_user;Password=core_secure_password_dev;Client Encoding=UTF8;
```

**RabbitMQ**
```text
amqp://rabbit_user:rabbit_secure_password_dev@localhost:5672/
```