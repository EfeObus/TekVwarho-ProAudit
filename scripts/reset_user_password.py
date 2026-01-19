#!/usr/bin/env python3
"""Reset user password."""
import asyncio
from sqlalchemy import select
from app.database import async_session_maker
from app.models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

async def reset_password():
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == 'efeobukohwo64@gmail.com')
        )
        user = result.scalar_one_or_none()
        if user:
            # Set new password
            new_password = 'Efeobus12345'
            user.hashed_password = pwd_context.hash(new_password)
            await session.commit()
            print(f'Password reset for {user.email}')
            print(f'New password: {new_password}')
        else:
            print('User not found!')

if __name__ == '__main__':
    asyncio.run(reset_password())
