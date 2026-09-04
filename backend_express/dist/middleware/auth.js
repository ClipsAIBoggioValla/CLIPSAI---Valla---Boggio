import jwt from 'jsonwebtoken';
function getSecret() {
    return process.env.JWT_SECRET ?? 'changeme';
}
function getAlgorithm() {
    return process.env.JWT_ALGORITHM ?? 'HS256';
}
export function authMiddleware(req, res, next) {
    const header = req.headers.authorization;
    if (!header || !header.startsWith('Bearer ')) {
        return res.status(401).json({ detail: 'Not authenticated' });
    }
    const token = header.slice(7);
    try {
        const payload = jwt.verify(token, getSecret(), { algorithms: [getAlgorithm()] });
        if (!payload.sub)
            throw new Error('no sub');
        req.user = { id: payload.sub };
        next();
    }
    catch (err) {
        if (err instanceof jwt.TokenExpiredError) {
            return res.status(401).json({ detail: 'Token expirado' });
        }
        return res.status(401).json({ detail: 'Token invalido' });
    }
}
