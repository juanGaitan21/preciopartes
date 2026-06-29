-- Usuario admin inicial (contraseña: admin123 — cambiar en producción)
INSERT INTO users (nombre, email, password_hash, rol) VALUES
    ('Administrador', 'admin@preciopartes.com',
     '$2b$12$1QhyuKwyv.KMQTK5F84Jd.D0t6PwGY3dTtUUeCGDYGZJJBrhtz48S', 'admin')
ON CONFLICT (email) DO NOTHING;
