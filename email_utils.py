"""Email utilities for UB eBallot."""
from flask_mail import Message
from app import mail


def send_otp_email(to_email: str, otp: str, election_title: str):
    """
    Send a one-time password to the student's UB institutional email.
    The OTP proves that the person entering the student number has access
    to the email account registered to that student number.
    """
    msg = Message(
        subject='UB eBallot — Your Voting Code',
        recipients=[to_email],
        html=f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;">
            <div style="background:#003087;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
                <h2 style="color:white;margin:0;">UB eBallot</h2>
                <p style="color:rgba(255,255,255,0.8);margin:4px 0 0;">University of Botswana SRC Elections</p>
            </div>
            <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0;">
                <p style="margin-top:0;">Your one-time voting code for <strong>{election_title}</strong>:</p>
                <div style="background:#fff;border:2px solid #003087;border-radius:8px;
                            padding:20px;text-align:center;margin:16px 0;">
                    <span style="font-size:2.5rem;font-weight:bold;letter-spacing:0.4rem;
                                 color:#003087;">{otp}</span>
                </div>
                <p style="font-size:0.85rem;color:#555;">
                    This code expires in <strong>10 minutes</strong> and can only be used once.
                </p>
                <p style="font-size:0.85rem;color:#c00;">
                    If you did not attempt to vote, someone may have your student number.
        
                </p>
            </div>
            <p style="font-size:0.75rem;color:#999;text-align:center;margin-top:12px;">
                University of Botswana SRC eBallot System
            </p>
        </div>
        """
    )
    mail.send(msg)
