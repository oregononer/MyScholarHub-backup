from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import ApplicantProfile

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer untuk registrasi Applicant baru."""
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        validators=[validate_password]  # Enforce Django password validators
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def create(self, validated_data):
        # Role SELALU APPLICANT — tidak bisa dioverride via request body
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role='APPLICANT'
        )
        # Auto-create ApplicantProfile kosong
        ApplicantProfile.objects.create(user=user)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer untuk menampilkan data profil user."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'profile_picture')
        read_only_fields = ('id', 'email', 'role')


class ApplicantProfileSerializer(serializers.ModelSerializer):
    """Serializer untuk profil tambahan Applicant."""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = ApplicantProfile
        fields = (
            'username', 'email', 'full_name', 'education_level',
            'current_institution', 'major', 'updated_at'
        )
        read_only_fields = ('updated_at',)


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer untuk ganti password — WAJIB verifikasi old_password."""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Password lama salah.')
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer untuk request reset password (lupa password)."""
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer untuk konfirmasi reset password dengan token."""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )