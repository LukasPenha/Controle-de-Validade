from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from .models import db, Produto, Usuario, Loja, Setor, ProdutoCatalogo
from datetime import datetime, date, time
from sqlalchemy import cast, Date
import io
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

routes = Blueprint('routes', __name__)

# --- FUNÇÃO HELPER PARA DESENHAR O PDF ---
def draw_pdf_report(buffer, titulo_principal, subtitulo, lista_produtos):
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    p.setTitle(titulo_principal)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(inch, height - inch, titulo_principal)
    p.setFont("Helvetica", 10)
    p.drawString(inch, height - inch - 20, subtitulo)
    y = height - inch - 60
    p.setFont("Helvetica-Bold", 9)
    p.drawString(inch, y, "Cadastrado Por")
    p.drawString(inch + 100, y, "Data Cadastro")
    p.drawString(inch + 200, y, "Nome do Produto")
    p.drawString(inch + 400, y, "Validade")
    p.drawString(inch + 480, y, "Status")
    y -= 5; p.line(inch, y, width - inch, y)
    p.setFont("Helvetica", 8); y -= 15
    if not lista_produtos:
        p.drawString(inch, y, "Nenhum produto encontrado para os filtros selecionados.")
    else:
        for produto_dict in lista_produtos:
            if y < inch:
                p.showPage(); y = height - inch - 20; p.setFont("Helvetica-Bold", 10); p.drawString(inch, y, "Continuação..."); y -= 25
            p.drawString(inch, y, produto_dict['criado_por'])
            p.drawString(inch + 100, y, produto_dict['data_cadastro'])
            p.drawString(inch + 200, y, produto_dict['nome_produto'])
            p.drawString(inch + 400, y, produto_dict['validade'])
            p.drawString(inch + 480, y, produto_dict['status'])
            y -= 15
    p.showPage()
    p.save()

# --- ROTA PRINCIPAL E DASHBOARDS ---

@routes.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    role_dashboard_map = {
        'gerente_geral': 'routes.dashboard_gerente_geral',
        'gerente_trocas': 'routes.dashboard_gerente_trocas',
        'gerente': 'routes.dashboard_gerente',
        'encarregado_setor': 'routes.listar_produtos_encarregado',
        'auxiliar_gestao': 'routes.dashboard_auxiliar'
    }
    dashboard_route = role_dashboard_map.get(current_user.role)
    if dashboard_route:
        return redirect(url_for(dashboard_route))
    
    flash('Seu cargo ainda não possui um dashboard definido.', 'info')
    return redirect(url_for('auth.login'))

@routes.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# --- ROTAS DO GERENTE GERAL ---
@routes.route('/gerente-geral/dashboard')
@login_required
def dashboard_gerente_geral():
    if current_user.role != 'gerente_geral': return redirect(url_for('routes.index'))
    return render_template('gerente_geral/dashboard.html')

@routes.route('/gerente-geral/lojas', methods=['GET', 'POST'])
@login_required
def gerenciar_lojas():
    if current_user.role != 'gerente_geral': return redirect(url_for('routes.index'))
    if request.method == 'POST':
        nome = request.form.get('nome')
        if Loja.query.filter_by(nome=nome).first():
            flash(f'Uma loja com o nome "{nome}" já existe.', 'warning')
        else:
            nova_loja = Loja(nome=nome, cnpj=request.form.get('cnpj'), endereco=request.form.get('endereco'), cidade=request.form.get('cidade'), estado=request.form.get('estado'))
            db.session.add(nova_loja)
            db.session.commit()
            flash(f'Loja "{nome}" criada com sucesso!', 'success')
        return redirect(url_for('routes.gerenciar_lojas'))
    lojas = Loja.query.order_by(Loja.nome).all()
    return render_template('gerente_geral/gerenciar_lojas.html', lojas=lojas)

@routes.route('/gerente-geral/loja/editar/<int:loja_id>', methods=['POST'])
@login_required
def editar_loja(loja_id):
    if current_user.role != 'gerente_geral': return redirect(url_for('routes.index'))
    loja = Loja.query.get_or_404(loja_id)
    loja.nome, loja.cnpj, loja.endereco, loja.cidade, loja.estado = request.form.get('nome'), request.form.get('cnpj'), request.form.get('endereco'), request.form.get('cidade'), request.form.get('estado')
    db.session.commit()
    flash('Dados da loja atualizados com sucesso!', 'success')
    return redirect(url_for('routes.gerenciar_lojas'))

@routes.route('/gerente-geral/loja/excluir/<int:loja_id>', methods=['POST'])
@login_required
def excluir_loja(loja_id):
    if current_user.role != 'gerente_geral': return redirect(url_for('routes.index'))
    loja_para_excluir = Loja.query.get_or_404(loja_id)
    if loja_para_excluir.usuarios:
        flash(f'Não é possível excluir a loja "{loja_para_excluir.nome}", pois ela possui usuários vinculados.', 'danger')
    else:
        db.session.delete(loja_para_excluir)
        db.session.commit()
        flash(f'Loja "{loja_para_excluir.nome}" foi excluída com sucesso.', 'success')
    return redirect(url_for('routes.gerenciar_lojas'))

@routes.route('/gerente-geral/usuarios', methods=['GET', 'POST'])
@login_required
def gerenciar_usuarios_geral():
    if current_user.role != 'gerente_geral': return redirect(url_for('routes.index'))
    if request.method == 'POST':
        username, password, role, loja_id, setor_id = request.form.get('username'), request.form.get('password'), request.form.get('role'), request.form.get('loja_id'), request.form.get('setor_id')
        if Usuario.query.filter_by(username=username).first():
            flash(f'O e-mail "{username}" já está em uso.', 'warning')
        else:
            loja_id = int(loja_id) if loja_id and loja_id.isdigit() else None
            setor_id = int(setor_id) if setor_id and setor_id.isdigit() else None
            if role == 'gerente_trocas': loja_id = None
            if role != 'encarregado_setor': setor_id = None
            novo_usuario = Usuario(username=username, role=role, loja_id=loja_id, setor_id=setor_id)
            novo_usuario.set_password(password)
            db.session.add(novo_usuario)
            db.session.commit()
            flash(f'Usuário "{username}" criado com sucesso!', 'success')
        return redirect(url_for('routes.gerenciar_usuarios_geral'))
    usuarios = Usuario.query.filter(Usuario.role != 'gerente_geral').order_by(Usuario.loja_id).all()
    lojas = Loja.query.all()
    setores = Setor.query.all()
    return render_template('gerente_geral/gerenciar_usuarios.html', usuarios=usuarios, lojas=lojas, setores=setores)

@routes.route('/gerente-geral/usuario/editar/<int:usuario_id>', methods=['POST'])
@login_required
def editar_usuario(usuario_id):
    if current_user.role != 'gerente_geral': return redirect(url_for('routes.index'))
    usuario = Usuario.query.get_or_404(usuario_id)
    usuario.username, usuario.role, loja_id, setor_id = request.form.get('username'), request.form.get('role'), request.form.get('loja_id'), request.form.get('setor_id')
    usuario.loja_id = int(loja_id) if loja_id and loja_id.isdigit() else None
    usuario.setor_id = int(setor_id) if setor_id and setor_id.isdigit() else None
    if usuario.role == 'gerente_trocas': usuario.loja_id = None
    if usuario.role != 'encarregado_setor': usuario.setor_id = None
    db.session.commit()
    flash('Usuário atualizado com sucesso!', 'success')
    return redirect(url_for('routes.gerenciar_usuarios_geral'))

@routes.route('/gerente-geral/usuario/excluir/<int:usuario_id>', methods=['POST'])
@login_required
def excluir_usuario(usuario_id):
    if current_user.role != 'gerente_geral': return redirect(url_for('routes.index'))
    usuario_para_excluir = Usuario.query.get_or_404(usuario_id)
    db.session.delete(usuario_para_excluir)
    db.session.commit()
    flash(f'Usuário "{usuario_para_excluir.username}" foi excluído.', 'success')
    return redirect(url_for('routes.gerenciar_usuarios_geral'))


# --- ROTAS DOS OUTROS CARGOS ---

@routes.route('/gerente/dashboard')
@login_required
def dashboard_gerente():
    if current_user.role != 'gerente': return redirect(url_for('routes.index'))
    produtos_para_rebaixa = Produto.query.filter(Produto.loja_id == current_user.loja_id, Produto.status == 'Para Rebaixa', Produto.validade >= date.today()).order_by(Produto.validade).all()
    produtos_em_rebaixa = Produto.query.filter(Produto.loja_id == current_user.loja_id, Produto.status == 'Em Rebaixa', Produto.validade >= date.today()).order_by(Produto.validade).all()
    return render_template('gerente/dashboard_gerente.html', produtos_para_rebaixa=produtos_para_rebaixa, produtos_em_rebaixa=produtos_em_rebaixa, now=datetime.now())

@routes.route('/gerente/cadastrar')
@login_required
def cadastrar_produto_gerente():
    if current_user.role != 'gerente': return redirect(url_for('routes.index'))
    setores = Setor.query.order_by(Setor.nome).all()
    return render_template('gerente/cadastrar_produto.html', setores=setores)

@routes.route('/encarregado/produtos')
@login_required
def listar_produtos_encarregado():
    if current_user.role != 'encarregado_setor': return redirect(url_for('routes.index'))
    produtos = Produto.query.filter(Produto.loja_id == current_user.loja_id, Produto.setor_id == current_user.setor_id, Produto.validade >= date.today()).order_by(Produto.validade).all()
    return render_template('encarregado/listar_produtos.html', produtos=produtos, now=datetime.now())

@routes.route('/encarregado/cadastrar')
@login_required
def cadastrar_produto_encarregado():
    if current_user.role != 'encarregado_setor': return redirect(url_for('routes.index'))
    return render_template('encarregado/cadastrar_produto.html')

@routes.route('/encarregado/vencidos')
@login_required
def vencidos_encarregado():
    if current_user.role != 'encarregado_setor': return redirect(url_for('routes.index'))
    produtos_vencidos = Produto.query.filter(Produto.loja_id == current_user.loja_id, Produto.setor_id == current_user.setor_id, Produto.validade < date.today()).order_by(Produto.validade.desc()).all()
    return render_template('encarregado/produtos_vencidos.html', produtos=produtos_vencidos, today=date.today())

@routes.route('/auxiliar/dashboard')
@login_required
def dashboard_auxiliar():
    if current_user.role != 'auxiliar_gestao': return redirect(url_for('routes.index'))
    setores = Setor.query.all()
    return render_template('auxiliar/dashboard_auxiliar.html', setores=setores)

@routes.route('/gerente-trocas/dashboard')
@login_required
def dashboard_gerente_trocas():
    if current_user.role != 'gerente_trocas': return redirect(url_for('routes.index'))
    lojas = Loja.query.order_by(Loja.nome).all()
    setores = Setor.query.order_by(Setor.nome).all()
    return render_template('gerente_trocas/dashboard_trocas.html', lojas=lojas, setores=setores)

@routes.route('/produtos/vencidos')
@login_required
def pagina_produtos_vencidos():
    if current_user.role not in ['gerente', 'gerente_geral', 'gerente_trocas']: return redirect(url_for('routes.index'))
    query = Produto.query.filter(Produto.validade < date.today())
    if current_user.role == 'gerente':
        query = query.filter(Produto.loja_id == current_user.loja_id)
        produtos_vencidos = query.order_by(Produto.validade.desc()).all()
        return render_template('gerente/produtos_vencidos.html', produtos=produtos_vencidos, today=date.today())
    produtos_vencidos = query.order_by(Produto.loja_id, Produto.validade.desc()).all()
    return render_template('geral/produtos_vencidos.html', produtos=produtos_vencidos, today=date.today())

# --- ROTAS DE AÇÕES DE PRODUTOS ---

@routes.route('/produtos', methods=['POST'])
@login_required
def cadastrar_produto():
    if current_user.role not in ['gerente', 'encarregado_setor', 'auxiliar_gestao']:
        flash('Você não tem permissão para cadastrar produtos.', 'danger')
        return redirect(url_for('routes.index'))
    nome_produto, plu, barcode, quantidade, validade_str, motivo_rebaixa, setor_id = request.form.get('nome_produto'), request.form.get('plu'), request.form.get('barcode'), request.form.get('quantidade'), request.form.get('validade'), request.form.get('motivo_rebaixa'), request.form.get('setor_id')
    if current_user.role == 'encarregado_setor': setor_id = current_user.setor_id
    if not all([nome_produto, plu, quantidade, validade_str, setor_id]):
        flash('Todos os campos, incluindo o setor, são obrigatórios.', 'danger')
        return redirect(request.referrer)
    if barcode:
        catalogo_item = ProdutoCatalogo.query.filter_by(barcode=barcode).first()
        if catalogo_item:
            catalogo_item.nome_produto, catalogo_item.plu = nome_produto, plu
        else:
            db.session.add(ProdutoCatalogo(barcode=barcode, nome_produto=nome_produto, plu=plu))
    novo_produto = Produto(nome_produto=nome_produto, plu=plu, quantidade=int(quantidade), validade=datetime.strptime(validade_str, '%Y-%m-%d').date(), motivo_rebaixa=motivo_rebaixa, setor_id=int(setor_id), loja_id=current_user.loja_id, criado_por_id=current_user.id)
    db.session.add(novo_produto)
    db.session.commit()
    flash('Produto cadastrado com sucesso e catálogo interno atualizado!', 'success')
    if current_user.role == 'gerente': return redirect(url_for('routes.cadastrar_produto_gerente'))
    elif current_user.role == 'encarregado_setor': return redirect(url_for('routes.cadastrar_produto_encarregado'))
    else: return redirect(url_for('routes.dashboard_auxiliar'))

@routes.route('/produtos/<int:produto_id>/editar', methods=['POST'])
@login_required
def editar_produto(produto_id):
    if current_user.role != 'encarregado_setor': return redirect(url_for('routes.index'))
    produto = Produto.query.get_or_404(produto_id)
    if produto.loja_id != current_user.loja_id or produto.setor_id != current_user.setor_id:
        flash('Você só pode editar produtos do seu setor.', 'danger')
        return redirect(url_for('routes.listar_produtos_encarregado'))
    produto.nome_produto, produto.plu, produto.quantidade, produto.validade, produto.motivo_rebaixa = request.form.get('nome_produto'), request.form.get('plu'), int(request.form.get('quantidade')), datetime.strptime(request.form.get('validade'), '%Y-%m-%d').date(), request.form.get('motivo_rebaixa')
    db.session.commit()
    flash('Produto atualizado com sucesso!', 'success')
    return redirect(url_for('routes.listar_produtos_encarregado'))

@routes.route('/produtos/<int:produto_id>/status', methods=['POST'])
@login_required
def alterar_status(produto_id):
    if current_user.role != 'gerente': return redirect(url_for('routes.index'))
    produto = Produto.query.get_or_404(produto_id)
    if produto.loja_id != current_user.loja_id: return redirect(url_for('routes.dashboard_gerente'))
    novo_status = request.form.get('status')
    if novo_status in ['Para Rebaixa', 'Em Rebaixa']:
        produto.status = novo_status
        db.session.commit()
        flash(f'Status do produto {produto.nome_produto} alterado.', 'success')
    else: flash('Status inválido.', 'danger')
    return redirect(url_for('routes.dashboard_gerente'))

@routes.route('/produtos/<int:produto_id>/excluir', methods=['POST'])
@login_required
def excluir_produto(produto_id):
    if current_user.role not in ['encarregado_setor', 'gerente_geral']: return redirect(url_for('routes.index'))
    produto = Produto.query.get_or_404(produto_id)
    if current_user.role == 'encarregado_setor' and (produto.loja_id != current_user.loja_id or produto.setor_id != current_user.setor_id):
        return redirect(url_for('routes.listar_produtos_encarregado'))
    db.session.delete(produto)
    db.session.commit()
    flash('Produto excluído com sucesso!', 'success')
    return redirect(request.referrer or url_for('routes.index'))


# --- ROTAS DE RELATÓRIOS E API ---

@routes.route('/encarregado/relatorio/pdf')
@login_required
def gerar_relatorio_encarregado_pdf():
    if current_user.role != 'encarregado_setor': return redirect(url_for('routes.index'))
    data_inicio_str, data_fim_str = request.args.get('data_inicio'), request.args.get('data_fim')
    if not data_inicio_str or not data_fim_str:
        flash('Datas são obrigatórias.', 'danger')
        return redirect(url_for('routes.listar_produtos_encarregado'))
    start_datetime = datetime.combine(datetime.strptime(data_inicio_str, '%Y-%m-%d').date(), time.min)
    end_datetime = datetime.combine(datetime.strptime(data_fim_str, '%Y-%m-%d').date(), time.max)
    produtos_db = Produto.query.join(Usuario).filter(Produto.loja_id == current_user.loja_id, Produto.setor_id == current_user.setor_id, Produto.data_cadastro.between(start_datetime, end_datetime)).order_by(Produto.data_cadastro).all()
    lista_simples = [{'criado_por': p.criado_por.nome_display, 'data_cadastro': p.data_cadastro.strftime('%d/%m/%Y'), 'nome_produto': p.nome_produto[:45], 'validade': p.validade.strftime('%d/%m/%Y'), 'status': p.status} for p in produtos_db]
    buffer = io.BytesIO()
    draw_pdf_report(buffer, f"Relatório do Setor: {current_user.setor.nome}", f"Produtos cadastrados de {data_inicio_str} a {data_fim_str}", lista_simples)
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': 'inline;filename=relatorio_setor.pdf'})

@routes.route('/gerente/relatorio/pdf')
@login_required
def gerar_relatorio_gerente_pdf():
    if current_user.role != 'gerente': return redirect(url_for('routes.index'))
    data_inicio_str, data_fim_str = request.args.get('data_inicio'), request.args.get('data_fim')
    if not data_inicio_str or not data_fim_str:
        flash('Datas são obrigatórias.', 'danger')
        return redirect(url_for('routes.dashboard_gerente'))
    start_datetime = datetime.combine(datetime.strptime(data_inicio_str, '%Y-%m-%d').date(), time.min)
    end_datetime = datetime.combine(datetime.strptime(data_fim_str, '%Y-%m-%d').date(), time.max)
    produtos_db = Produto.query.join(Usuario).filter(Produto.loja_id == current_user.loja_id, Produto.data_cadastro.between(start_datetime, end_datetime)).order_by(Produto.setor_id, Produto.data_cadastro).all()
    lista_simples = [{'criado_por': p.criado_por.nome_display, 'data_cadastro': p.data_cadastro.strftime('%d/%m/%Y'), 'nome_produto': p.nome_produto[:45], 'validade': p.validade.strftime('%d/%m/%Y'), 'status': p.status} for p in produtos_db]
    buffer = io.BytesIO()
    draw_pdf_report(buffer, f"Relatório da Loja: {current_user.loja.nome}", f"Produtos cadastrados de {data_inicio_str} a {data_fim_str}", lista_simples)
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': 'inline;filename=relatorio_loja.pdf'})

@routes.route('/relatorio/pdf')
@login_required
def gerar_relatorio_pdf():
    if current_user.role not in ['gerente_geral', 'gerente_trocas']: return redirect(url_for('routes.index'))
    data_inicio_str, data_fim_str, loja_id, setor_id = request.args.get('data_inicio'), request.args.get('data_fim'), request.args.get('loja_id'), request.args.get('setor_id')
    if not data_inicio_str or not data_fim_str:
        flash('Datas são obrigatórias.', 'danger')
        return redirect(request.referrer)
    start_datetime = datetime.combine(datetime.strptime(data_inicio_str, '%Y-%m-%d').date(), time.min)
    end_datetime = datetime.combine(datetime.strptime(data_fim_str, '%Y-%m-%d').date(), time.max)
    query = Produto.query.join(Usuario).filter(Produto.data_cadastro.between(start_datetime, end_datetime))
    if loja_id and loja_id != 'todas': query = query.filter(Produto.loja_id == int(loja_id))
    if setor_id and setor_id != 'todos': query = query.filter(Produto.setor_id == int(setor_id))
    produtos_db = query.order_by(Produto.loja_id, Produto.setor_id, Produto.data_cadastro).all()
    lista_simples = [{'criado_por': p.criado_por.nome_display, 'data_cadastro': p.data_cadastro.strftime('%d/%m/%Y'), 'nome_produto': p.nome_produto[:45], 'validade': p.validade.strftime('%d/%m/%Y'), 'status': p.status} for p in produtos_db]
    buffer = io.BytesIO()
    draw_pdf_report(buffer, "Relatório Geral de Produtos", f"Produtos cadastrados de {data_inicio_str} a {data_fim_str}", lista_simples)
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': 'inline;filename=relatorio_geral_cadastro.pdf'})


@routes.route('/api/buscar-produto/<string:barcode>')
@login_required
def api_buscar_produto(barcode):
    produto_catalogo = ProdutoCatalogo.query.filter_by(barcode=barcode).first()
    if produto_catalogo:
        return jsonify({"nome": produto_catalogo.nome_produto, "plu": produto_catalogo.plu or barcode, "encontrado": True, "fonte": "Catálogo Interno"})
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == 1 and data.get("product"):
                produto = data.get("product")
                nome = produto.get("product_name_pt") or produto.get("product_name", "")
                return jsonify({"nome": nome.strip(), "plu": barcode, "encontrado": True, "fonte": "Open Food Facts"})
    except requests.exceptions.RequestException:
        return jsonify({"encontrado": False, "mensagem": "Erro de conexão com a API."})
    return jsonify({"encontrado": False, "mensagem": "Produto não encontrado."})