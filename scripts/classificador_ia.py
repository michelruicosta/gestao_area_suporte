# classificador_ia.py
# O que faz: recebe uma thread (todas as mensagens em ordem cronológica),
#             lê o texto de cada mensagem e decide:
#               - Com a Finaud (aguarda ação interna)
#               - Com o cliente (aguarda resposta do cliente)
#               - Concluída (o assunto foi resolvido)
#             Retorna a classificação com o motivo em linguagem clara.
#
# Substitui: o motor de triagem por regex (scripts/triagem/ — arquivado)
# Entrada:   thread com mensagens no formato entregue pelo coletor_gmail.py
# Saída:     { estado, motivo, quem_age, ultima_acao }
#
# TODO: implementar após fechar a especificação (campos 6, 7, 8 da spec)
