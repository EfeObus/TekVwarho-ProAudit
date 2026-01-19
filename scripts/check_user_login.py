#!/usr/bin/env python3
"""Check user login credentials."""
import asyncio
from sqlalchemy import select
from app.database import async_session_maker
from app.models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

async def check_password():
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == 'efeobukohwo64@gmail.com')
        )
        user = result.scalar_one_or_none()
        if user:
            print(f'User found: {user.email}')
            print(f'Verified: {user.is_verified}')
            print(f'Active: {user.is_active}')
            print(f'Role: {user.role}')
            
            # Test password
            test_password = 'Efeobus12345'
            is_valid = pwd_context.verify(test_password, user.hashed_password)
            print(f'Password "Efeobus12345" valid: {is_valid}')
        else:
            print('User not found!')

if __name__ == '__main__':
    asyncio.run(check_password())
