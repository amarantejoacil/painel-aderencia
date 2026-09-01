class AzureDevOpsError(Exception):
    """Erro genérico na integração com Azure DevOps."""


class AzureDevOpsConfigError(AzureDevOpsError):
    """Configuração incompleta ou inválida."""


class AzureDevOpsAuthError(AzureDevOpsError):
    """Falha de autenticação ou permissão."""


class AzureDevOpsConnectionError(AzureDevOpsError):
    """Falha de rede ou serviço indisponível."""
