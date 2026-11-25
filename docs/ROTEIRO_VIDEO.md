# Roteiro falado para o vídeo de demonstração (aprox. 5 minutos)

Use este texto como guia. Fale naturalmente e mostre a tela na ordem pedida pelo desafio.

## 1. Apresentação da arquitetura — 0:00 a 0:40

“Este projeto é o HelpDesk TI, que originalmente funcionava como um monólito. Na nova arquitetura, a tela acessa um único ponto de entrada, o API Gateway, na porta 8000. O Gateway encaminha as requisições para três microsserviços independentes: Usuários, Inventário e Chamados. Cada serviço tem seu próprio banco de dados. O serviço de Chamados conversa com Usuários e Inventário por HTTP quando precisa validar um técnico ou um equipamento. Assim, os serviços não acessam diretamente os bancos uns dos outros.”

Mostre o diagrama da seção Arquitetura no README.

## 2. Subida dos contêineres — 0:40 a 1:10

No terminal, na pasta do repositório, execute:

```bash
docker compose up --build
```

Em outro terminal, na mesma pasta, mostre:

```bash
docker compose ps
```

“Os quatro contêineres estão em execução. Só o Gateway publica a porta 8000 para o computador. Os serviços de Usuários, Inventário e Chamados ficam acessíveis apenas pela rede Docker.”

## 3. Fluxo completo do chamado — 1:10 a 2:20

Abra `http://localhost:8000`, entre com `carla@empresa.com` e senha `Helpdesk2026`. Crie um chamado com equipamento, atribua à técnica Carla, resolva e feche.

“Estou usando o endereço do Gateway, sem acessar diretamente nenhum microsserviço. O chamado é salvo no banco de Chamados. Ao selecionar um equipamento, Chamados consulta o Inventário pela rede. Ao atribuir, consulta Usuários para confirmar que o perfil informado é de técnico. As regras de SLA e de transição de status continuam funcionando.”

## 4. Segurança — 2:20 a 3:00

Em um terminal, mostre que não existe acesso sem token:

```bash
curl -i http://localhost:8000/chamados
```

A resposta esperada é `401 Unauthorized`.

Para provar o isolamento entre solicitantes, primeiro obtenha o token de Ana:

```bash
ANA_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"ana@empresa.com","senha":"Helpdesk2026"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Com os dados de exemplo recém-criados, o chamado `2` pertence a Bruno. Faça:

```bash
curl -i http://localhost:8000/chamados/2 \
  -H "Authorization: Bearer $ANA_TOKEN"
```

A resposta esperada é `404 Not Found`, pois Ana não pode consultar o chamado de Bruno.

“Os serviços validam a assinatura e a validade do JWT. As permissões por perfil continuam aplicadas e o token é encaminhado nas chamadas internas.”

## 5. Bancos separados — 3:00 a 3:30

Execute:

```bash
docker volume ls
```

Mostre os volumes `dados_usuarios`, `dados_inventario` e `dados_chamados` (o Compose pode acrescentar o nome da pasta como prefixo).

“Cada microsserviço persiste seus próprios dados. O serviço de Chamados guarda os identificadores de usuário e ativo, mas não cria chaves estrangeiras para tabelas de outros bancos.”

## 6. Falha do Inventário — 3:30 a 4:30

Com a interface aberta e autenticada, em outro terminal execute:

```bash
docker compose stop inventario
```

Atualize a tela. Mostre que os usuários e a lista de chamados continuam aparecendo. Tente abrir um chamado escolhendo um equipamento: a operação deve exibir a mensagem de indisponibilidade do Inventário e a API deve responder 503.

“Como o Inventário está fora do ar, Chamados não consegue validar o equipamento. Em vez de ficar esperando sem limite ou travar, a aplicação retorna um erro 503 claro. As funções que não dependem do Inventário continuam disponíveis.”

Restaure o serviço:

```bash
docker compose start inventario
docker compose ps
```

Espere o Inventário aparecer como saudável antes de testar novamente.

## 7. Conclusão e testes — 4:30 a 5:20

“Em relação ao monólito, agora cada serviço pode evoluir e ser implantado de forma independente, e cada um controla seus dados. A arquitetura também ficou mais complexa: existe comunicação pela rede, timeout, tratamento de falhas e mais componentes para monitorar. Executei os testes automatizados e eles verificam as regras funcionais, a autenticação e as fronteiras entre os serviços.”

Mostre, se couber no tempo:

```bash
pytest -q
```

Encerre explicando que a fila assíncrona de eventos é uma possível evolução futura e não foi implementada nesta versão.
