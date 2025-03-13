import random
import time
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from google.api_core.exceptions import ResourceExhausted  # Hata tipini import ediyoruz
from colorama import Fore, Style

class Agent:
    def __init__(self, name, role):
        self.name = name
        self.role = role  # 'villager' veya 'vampire'
        self.is_alive = True
        # Her agent için ayrı bir Gemini-2.0 Flash modeli örneği
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    
    def safe_invoke(self, chain, inputs):
        """Quota (kaynak) hatası alındığında 5 saniye bekleyip yeniden denemek için yardımcı fonksiyon."""
        while True:
            try:
                response = chain.invoke(inputs)
                return response
            except ResourceExhausted:
                print(f"{self.name}: Resource exhausted, waiting 5 seconds and retrying.")
                time.sleep(5)
    
    def speak(self, phase, extra_input=""):
        """
        Belirtilen aşamaya göre mesaj üretir. Prompt içerisinde {input} placeholder'ı kullanılır.
        """
        if phase == "morning":
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an agent in a village game. It's morning. Express your initial thoughts naturally."),
                ("human", "{input}")
            ])
        elif phase == "defense":
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an agent in a village game. It's time for your defense. Respond naturally and convincingly, defending your innocence. If anyone has accused you, address their concerns. In your response, do not leave any placeholder or bracketed instructions. Instead, replace any indication like [mention your role-related activity, e.g., gathering resources, tending to the crops, helping the children] with a specific, concrete detail from your role-related activities."),
                ("human", "{input}")
            ])
        elif phase == "vampire":
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a vampire in a village game. In your secret chat, express your suspicions about who might be a villager and propose a candidate for elimination."),
                ("human", "{input}")
            ])
        elif phase == "vote":
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an agent in a village game. It is time to vote for elimination. Analyze the behavior and statements of your fellow agents. You must NOT vote for yourself. Cast your vote by providing both the candidate's name and a clear, specific explanation based on observed behaviors or statements. If there is no glaringly suspicious behavior, explain your reasoning based on the discussion dynamics. Use the format: 'CandidateName: Explanation'. Do not include extraneous phrases like 'My reasoning' or 'Your reasoning'."),
                ("human", "{input}")
            ])
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Express your thoughts."),
                ("human", "{input}")
            ])
        chain = prompt | self.llm
        response = self.safe_invoke(chain, {"input": extra_input})
        return response.content
    
    def select_candidate(self, candidates):
        """
        Vampirler için: Hayatta olan köylüler arasından şüphelenilen adayın ismini belirler.
        """
        candidate_list_str = ", ".join(candidates)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a vampire in a village game. From the following list of candidates, choose the one you suspect most to be a true villager. Provide only the candidate's name."),
            ("human", "Candidates: {candidates}")
        ])
        chain = prompt | self.llm
        response = self.safe_invoke(chain, {"candidates": candidate_list_str})
        candidate = response
        return candidate
    
    def revise_candidate(self, other_candidate, candidates):
        """
        Vampirler için: Eğer vampirlerin ilk aday seçimleri farklıysa, ortak karar sağlamak amacıyla aday revizesi yapılır.
        """
        candidate_list_str = ", ".join(candidates)
        prompt_text = (
            f"Your colleague suggested eliminating '{other_candidate}', but you might have a different opinion. "
            f"Given the candidates: {candidate_list_str}, propose a revised candidate that both of you could agree upon. Provide only the candidate's name."
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Discuss with your fellow vampire and propose a common target."),
            ("human", "{input}")
        ])
        chain = prompt | self.llm
        response = self.safe_invoke(chain, {"input": prompt_text})
        candidate = response
        return candidate

class Game:
    def __init__(self, vampire_count=2, villager_count=6):
        self.agents = []
        self.round = 0
        self.vampire_count = vampire_count
        self.villager_count = villager_count
        self.setup_agents()
    
    def setup_agents(self):
        """
        8 agent oluşturulur: 6 köylü, 2 vampir. Roller rastgele dağıtılır.
        """
        roles = ['villager'] * self.villager_count + ['vampire'] * self.vampire_count
        random.shuffle(roles)
        for i, role in enumerate(roles, start=1):
            self.agents.append(Agent(name=f"Agent {i}", role=role))
        # Renkleri atama: Vampirler için farklı kırmızı tonları, köylüler için farklı renkler
        vampire_colors = [Fore.LIGHTRED_EX, Fore.RED, Fore.MAGENTA]
        villager_colors = [Fore.CYAN, Fore.GREEN, Fore.BLUE, Fore.LIGHTBLUE_EX, Fore.YELLOW, Fore.LIGHTGREEN_EX]
        
        v_index = 0
        vi_index = 0
        for agent in self.agents:
            if agent.role == 'vampire':
                agent.speech_color = vampire_colors[v_index % len(vampire_colors)]
                v_index += 1
            else:
                agent.speech_color = villager_colors[vi_index % len(villager_colors)]
                vi_index += 1

        print("Oyuncular oluşturuldu:")
        for agent in self.agents:
            role_name = "Vampir" if agent.role == 'vampire' else "Köylü"
            print(f"{agent.speech_color}{agent.name}: {role_name}{Style.RESET_ALL}\n")
    
    def get_alive_agents(self):
        return [agent for agent in self.agents if agent.is_alive]
    
    def get_alive_villagers(self):
        return [agent for agent in self.agents if agent.is_alive and agent.role == 'villager']
    
    def get_alive_vampires(self):
        return [agent for agent in self.agents if agent.is_alive and agent.role == 'vampire']
    
    def morning_chat(self):
        """
        Sabah sohbeti: Tüm hayatta olan agentlar, özgürce sabah mesajlarını üretir.
        """
        print("\n--- Sabah Sohbeti ---")
        for agent in self.get_alive_agents():
            message = agent.speak("morning", extra_input="Share your thoughts for the morning.")
            print(f"{agent.speech_color}{agent.name}: {message}{Style.RESET_ALL}\n")
            time.sleep(1)
    
    def defense_phase(self):
        """
        Savunma aşaması: Hayatta olan agentlar rastgele sırayla savunmalarını yapar.
        """
        print("\n--- Savunma Aşaması ---")
        alive_agents = self.get_alive_agents()
        random.shuffle(alive_agents)
        for agent in alive_agents:
            message = agent.speak("defense", extra_input="Defend yourself.")
            print(f"{agent.speech_color}{agent.name} (Savunma): {message}{Style.RESET_ALL}\n")
            time.sleep(1)

    def voting_phase(self):
        """
        Oylama aşaması: Tüm canlı agentlar, kimin elenmesi gerektiğine dair oy verir.
        Her ajan, adayın ismi ve neden o adayın seçildiğini açıklayan somut bir açıklama ile oy vermelidir.
        Kendi kendine oy vermeye izin verilmez. Geçerli formatta cevap alınamazsa, maksimum 3 deneme yapılır.
        En fazla oy alan elenir.
        """
        print("\n--- Oylama Aşaması ---")
        candidates = [agent.name for agent in self.get_alive_agents()]
        votes = {}
        
        for agent in self.get_alive_agents():
            valid_vote = False
            attempt = 0
            vote_response_text = ""
            while not valid_vote and attempt < 3:
                attempt += 1
                vote_response_text = agent.speak("vote", extra_input="Candidates: " + ", ".join(candidates))
                vote_response_text = vote_response_text.strip()
                parts = vote_response_text.split(":", 1)
                if len(parts) == 2:
                    candidate_vote = parts[0].strip()
                    explanation = parts[1].strip()
                    # Geçerli cevap kontrolü: aday ismi listede olmalı, oy veren kendisi olmamalı,
                    # açıklama boş olmamalı, en az 4 kelime içermeli ve istenmeyen ifadeler içermemeli.
                    if (candidate_vote in candidates and candidate_vote != agent.name and explanation and 
                        len(explanation.split()) >= 4 and
                        ("My reasoning" not in explanation and "Your reasoning" not in explanation)):
                        valid_vote = True
                        break
                # Geçersiz cevap alınırsa, ajana yeniden hatırlatma yapıyoruz.
                print(f"{agent.speech_color}{agent.name} (Oylama): Cevabınız geçerli formatta değil. Lütfen 'CandidateName: Explanation' formatında, ekstra ifadeler olmadan ve kendinize oy vermeden oy veriniz.{Style.RESET_ALL}\n")
                time.sleep(1)
            if not valid_vote:
                # Maksimum deneme sonrası geçerli cevap alınamazsa, kendisi hariç rastgele seçim yapılıyor.
                valid_candidates = [c for c in candidates if c != agent.name]
                candidate_vote = random.choice(valid_candidates) if valid_candidates else agent.name
                explanation = "Invalid vote response."
            print(f"{agent.speech_color}{agent.name} (Oylama): {candidate_vote} - {explanation}{Style.RESET_ALL}\n")
            votes[candidate_vote] = votes.get(candidate_vote, 0) + 1
            time.sleep(1)
        
        max_votes = max(votes.values())
        potential_targets = [name for name, count in votes.items() if count == max_votes]
        chosen_candidate = random.choice(potential_targets)
        print(f"\nOy birliği sonucu, en fazla oy alan: {chosen_candidate} eleniyor.\n")
        target_agent = next((agent for agent in self.get_alive_agents() if agent.name == chosen_candidate), None)
        if target_agent:
            target_agent.is_alive = False

    def night_phase(self):
        """
        Gece aşaması: Sadece vampirler gizli kanalda konuşur ve oy birliği olmadan hedef seçemezler.
        Vampirler önce bireysel adaylarını belirler, ardından fikir birliği sağlamak için tartışırlar.
        """
        print("\n--- Gece Aşaması (Vampirlerin Sırası) ---")
        vampires = self.get_alive_vampires()
        if not vampires:
            print("Vampir kalmadı. Gece aşaması atlanıyor.")
            return
        
        print("Vampirler gizli kanalda tartışıyor...\n")
        for vampire in vampires:
            message = vampire.speak("vampire", extra_input="Discuss your suspicions. Propose a candidate for elimination. Who would be perfect for raising suspicion on others?")
            print(f"{vampire.speech_color}{vampire.name} (Gizli): {message}{Style.RESET_ALL}\n")
            time.sleep(1)

        villagers = self.get_alive_villagers()
        if not villagers:
            print("Hayatta köylü kalmadı!")
            return
        
        candidate_names = [villager.name for villager in villagers]
        initial_choices = {}
        for vampire in vampires:
            choice = vampire.select_candidate(candidate_names)
            initial_choices[vampire.name] = choice.content
            print(f"{vampire.name} ilk tercihi: {choice.content}")
        
        if len(set(initial_choices.values())) == 1:
            chosen_candidate = list(initial_choices.values())[0]
            print(f"\nVampirler oy birliği ile {chosen_candidate}'yi hedef aldılar.")
        else:
            print("\nVampirler ilk turda fikir birliğine varamadılar, konsensüs sağlanıyor...")
            consensus_round = 0
            max_rounds = 3
            consensus_choices = initial_choices.copy()
            while len(set(consensus_choices.values())) > 1 and consensus_round < max_rounds:
                consensus_round += 1
                new_choices = {}
                for vampire in vampires:
                    other_choices = [consensus_choices[other.name] for other in vampires if other.name != vampire.name]
                    other_choice = other_choices[0] if other_choices else consensus_choices[vampire.name]
                    revised = vampire.revise_candidate(other_choice, candidate_names)
                    new_choices[vampire.name] = revised
                    print(f"{vampire.name} revize tercihi: {revised}")
                    time.sleep(1)
                consensus_choices = new_choices
            if len(set(consensus_choices.values())) == 1:
                chosen_candidate = list(consensus_choices.values())[0]
                print(f"\nKonsensüs sağlandı: {chosen_candidate} hedef alınıyor.")
            else:
                votes = {}
                for choice in consensus_choices.values():
                    votes[choice] = votes.get(choice, 0) + 1
                max_votes = max(votes.values())
                potential_targets = [name for name, count in votes.items() if count == max_votes]
                chosen_candidate = random.choice(potential_targets)
                print(f"\nKonsensüs sağlanamadı. Rastgele seçim ile {chosen_candidate} hedef olarak belirlendi.")
        
        target_agent = next((agent for agent in villagers if agent.name == chosen_candidate), None)
        if target_agent:
            target_agent.is_alive = False
            print(f"\nVampirler, {target_agent.name}'i oyundan elendi olarak işaretledi!")
    
    def show_status(self):
        """
        Oyundaki her agent’ın hayatta ya da elendi durumunu gösterir.
        """
        print("\n--- Oyun Durumu ---")
        for agent in self.agents:
            status = "Hayatta" if agent.is_alive else "Elendi"
            role_name = "Vampir" if agent.role == 'vampire' else "Köylü"
            print(f"{agent.speech_color}{agent.name} ({role_name}): {status}{Style.RESET_ALL}\n")
    
    def check_win_conditions(self):
        """
        Kazanma koşullarını kontrol eder:
          - Tüm vampirler elenmişse: Köylüler kazanır.
          - Vampir sayısı köylü sayısına eşit veya fazla ise: Vampirler kazanır.
        """
        vampires_alive = len(self.get_alive_vampires())
        villagers_alive = len(self.get_alive_villagers())
        if vampires_alive == 0:
            print("\nKöylüler kazandı! Tüm vampirler elendi.")
            return True
        if vampires_alive > villagers_alive:
            print("\nVampirler kazandı! Kontrol onlarındır.")
            return True
        return False
    
    def run_game(self):
        """
        Oyun döngüsü: Her tur sabah sohbeti, savunma ve gece aşamalarını içerir.
        """
        print("\nVampir Köylü Oyunu Başladı!")
        while True:
            self.round += 1
            print(f"\n===== TUR {self.round} =====")
            self.morning_chat()
            self.defense_phase()
            self.voting_phase()
            self.night_phase()
            self.show_status()
            if self.check_win_conditions():
                break
            time.sleep(2)
        print("\nOyun Bitti!")

if __name__ == "__main__":
    game = Game(vampire_count=2, villager_count=6)
    game.run_game()
